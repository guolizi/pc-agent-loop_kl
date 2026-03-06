"""
Voice Agent Integration Module
将语音控制功能集成到 GenericAgent 中
"""

import os
import sys
import time
import threading
import queue
from typing import Optional, Callable
from datetime import datetime

# 导入语音控制模块
try:
    from voice_control import (
        VoiceController, VoiceConfig, 
        create_default_voice_controller
    )
    VOICE_CONTROL_AVAILABLE = True
except ImportError as e:
    print(f"Voice control module import error: {e}")
    VOICE_CONTROL_AVAILABLE = False

# 导入Agent主模块
from agentmain import GeneraticAgent


class VoiceEnabledAgent:
    """
    支持语音交互的Agent包装类
    整合语音控制与GenericAgent的功能
    """
    
    def __init__(
        self,
        agent: Optional[GeneraticAgent] = None,
        wake_word: str = "你好助手",
        enable_tts: bool = True,
        enable_voice_input: bool = True,
        auto_start_voice: bool = False
    ):
        """
        初始化语音增强型Agent
        
        Args:
            agent: GenericAgent实例，如果为None则创建新实例
            wake_word: 唤醒词
            enable_tts: 是否启用语音合成（朗读回复）
            enable_voice_input: 是否启用语音输入
            auto_start_voice: 是否自动启动语音监听
        """
        # Agent实例
        self.agent = agent or GeneraticAgent()
        
        # 语音控制器
        self.voice_controller: Optional[VoiceController] = None
        
        # 配置
        self.wake_word = wake_word
        self.enable_tts = enable_tts
        self.enable_voice_input = enable_voice_input
        
        # 状态
        self.is_voice_active = False
        self.current_task_queue: Optional[queue.Queue] = None
        self.is_processing = False
        
        # 回调函数
        self.on_voice_input: Optional[Callable[[str], None]] = None
        self.on_agent_response: Optional[Callable[[str], None]] = None
        
        # 响应队列（用于流式输出）
        self.response_buffer = ""
        self.speak_queue = queue.Queue()
        self.speak_thread: Optional[threading.Thread] = None
        
        # 初始化
        self._init_voice_controller()
        
        # 自动启动
        if auto_start_voice and self.voice_controller:
            self.start_voice()
    
    def _init_voice_controller(self):
        """初始化语音控制器"""
        if not VOICE_CONTROL_AVAILABLE:
            print("Voice control not available. Please install required dependencies.")
            return
        
        try:
            # 创建语音控制器
            config = VoiceConfig(
                wake_word=self.wake_word,
                enable_interrupt=True
            )
            
            self.voice_controller = VoiceController(config)
            
            # 设置回调
            self.voice_controller.on_wake_word = self._on_wake_word
            self.voice_controller.on_speech_recognized = self._on_speech_recognized
            self.voice_controller.on_interrupt = self._on_interrupt
            
            print(f"Voice controller initialized with wake word: '{self.wake_word}'")
            
        except Exception as e:
            print(f"Failed to initialize voice controller: {e}")
            self.voice_controller = None
    
    def _on_wake_word(self):
        """唤醒词检测回调"""
        print(f"\n[Voice] Wake word detected! Listening...")
    
    def _on_speech_recognized(self, text: str):
        """语音识别回调"""
        if not text or not text.strip():
            return
        
        print(f"[Voice] Recognized: {text}")
        
        # 调用外部回调
        if self.on_voice_input:
            self.on_voice_input(text)
        
        # 提交任务给Agent
        self._submit_task(text)
    
    def _on_interrupt(self):
        """打断回调"""
        print("[Voice] Interrupt detected!")
        self.agent.abort()
        self.is_processing = False
    
    def _submit_task(self, query: str):
        """提交任务给Agent处理"""
        if self.is_processing:
            print("[Voice] Already processing a task, please wait...")
            if self.voice_controller and self.voice_controller.tts:
                self.voice_controller.speak("请稍等，我正在处理中", block=False)
            return
        
        self.is_processing = True
        
        # 提交任务
        self.current_task_queue = self.agent.put_task(query, source="voice")
        
        # 启动处理线程
        threading.Thread(target=self._process_response, daemon=True).start()
    
    def _process_response(self):
        """处理Agent响应"""
        try:
            full_response = ""
            last_speak_pos = 0
            
            while True:
                try:
                    item = self.current_task_queue.get(timeout=120)
                    
                    if 'next' in item:
                        # 流式输出
                        chunk = item['next']
                        full_response = item.get('next', '')
                        
                        # 检查是否需要朗读（按句子分割）
                        if self.enable_tts and self.voice_controller:
                            new_text = full_response[last_speak_pos:]
                            # 查找完整句子
                            sentences = self._extract_sentences(new_text)
                            if sentences:
                                for sentence in sentences:
                                    if len(sentence.strip()) > 5:  # 至少5个字符
                                        self._speak_text(sentence)
                                last_speak_pos = len(full_response)
                    
                    if 'done' in item:
                        # 完成
                        full_response = item['done']
                        
                        # 朗读剩余内容
                        if self.enable_tts and self.voice_controller:
                            remaining = full_response[last_speak_pos:]
                            if remaining.strip():
                                self._speak_text(remaining)
                        
                        # 调用回调
                        if self.on_agent_response:
                            self.on_agent_response(full_response)
                        
                        break
                
                except queue.Empty:
                    print("[Voice] Task timeout")
                    break
        
        except Exception as e:
            print(f"[Voice] Error processing response: {e}")
        
        finally:
            self.is_processing = False
            self.current_task_queue = None
    
    def _extract_sentences(self, text: str) -> list:
        """从文本中提取完整句子"""
        import re
        
        # 中文句子结束符
        sentence_endings = r'[。！？.!?;；]'
        
        # 分割句子
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if re.match(sentence_endings, char):
                if current.strip():
                    sentences.append(current.strip())
                current = ""
        
        return sentences
    
    def _speak_text(self, text: str):
        """将文本加入语音合成队列"""
        if not self.voice_controller or not self.enable_tts:
            return
        
        # 清理文本（移除markdown等）
        clean_text = self._clean_text_for_speech(text)
        
        if clean_text.strip():
            self.speak_queue.put(clean_text)
            
            # 启动语音合成线程（如果未运行）
            if not self.speak_thread or not self.speak_thread.is_alive():
                self.speak_thread = threading.Thread(target=self._speak_worker, daemon=True)
                self.speak_thread.start()
    
    def _speak_worker(self):
        """语音合成工作线程"""
        while True:
            try:
                text = self.speak_queue.get(timeout=0.5)
                
                # 检查是否被打断
                if self.voice_controller and self.voice_controller.interrupt_flag.is_set():
                    continue
                
                # 合成语音
                if self.voice_controller:
                    self.voice_controller.speak(text, block=True)
                
            except queue.Empty:
                break
            except Exception as e:
                print(f"[Voice] Speak error: {e}")
    
    def _clean_text_for_speech(self, text: str) -> str:
        """清理文本以便语音合成"""
        import re
        
        # 移除markdown代码块
        text = re.sub(r'```[\s\S]*?```', ' [代码] ', text)
        
        # 移除行内代码
        text = re.sub(r'`[^`]*`', ' [代码] ', text)
        
        # 移除URL
        text = re.sub(r'https?://\S+', ' [链接] ', text)
        
        # 移除markdown标记
        text = re.sub(r'[#*_\[\](){}]', ' ', text)
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def start_voice(self):
        """启动语音监听"""
        if not self.voice_controller:
            print("[Voice] Voice controller not available")
            return False
        
        if self.is_voice_active:
            print("[Voice] Already active")
            return True
        
        try:
            self.voice_controller.start()
            self.is_voice_active = True
            print(f"[Voice] Started listening for wake word: '{self.wake_word}'")
            print("[Voice] Say interrupt words (停/停止/等一下/打断) to stop speaking")
            return True
        except Exception as e:
            print(f"[Voice] Failed to start: {e}")
            return False
    
    def stop_voice(self):
        """停止语音监听"""
        if self.voice_controller:
            self.voice_controller.stop()
        
        self.is_voice_active = False
        print("[Voice] Stopped")
    
    def speak(self, text: str, block: bool = False):
        """
        手动语音合成
        
        Args:
            text: 要合成的文本
            block: 是否阻塞等待
        """
        if self.voice_controller:
            self.voice_controller.speak(text, block=block)
    
    def interrupt(self):
        """打断当前语音播放"""
        if self.voice_controller:
            self.voice_controller.interrupt()
        self.agent.abort()
    
    def set_wake_word(self, wake_word: str):
        """设置新的唤醒词"""
        self.wake_word = wake_word
        if self.voice_controller:
            self.voice_controller.config.wake_word = wake_word
            self.voice_controller.wake_detector.wake_words = [wake_word.lower()]
    
    def set_tts_voice(self, voice_id: str):
        """设置TTS音色"""
        if self.voice_controller and self.voice_controller.tts:
            self.voice_controller.tts.set_voice(voice_id)
    
    def set_tts_rate(self, rate: int):
        """设置TTS语速"""
        if self.voice_controller and self.voice_controller.tts:
            self.voice_controller.tts.set_rate(rate)
    
    def set_tts_volume(self, volume: float):
        """设置TTS音量"""
        if self.voice_controller and self.voice_controller.tts:
            self.voice_controller.tts.set_volume(volume)
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "voice_active": self.is_voice_active,
            "voice_ready": self.voice_controller.is_ready() if self.voice_controller else False,
            "processing": self.is_processing,
            "wake_word": self.wake_word,
            "tts_enabled": self.enable_tts,
            "voice_input_enabled": self.enable_voice_input,
        }
    
    def run_cli(self):
        """运行命令行交互界面（支持语音）"""
        print("\n" + "="*60)
        print("Voice-Enabled GenericAgent")
        print("="*60)
        print(f"Wake word: '{self.wake_word}'")
        print("Commands:")
        print("  /voice on    - Enable voice input")
        print("  /voice off   - Disable voice input")
        print("  /speak on    - Enable text-to-speech")
        print("  /speak off   - Disable text-to-speech")
        print("  /wake <word> - Change wake word")
        print("  /interrupt   - Interrupt current task")
        print("  /status      - Show status")
        print("  /quit        - Exit")
        print("="*60 + "\n")
        
        # 启动Agent后台线程
        if not hasattr(self.agent, '_started'):
            threading.Thread(target=self.agent.run, daemon=True).start()
            self.agent._started = True
        
        # 启动语音
        self.start_voice()
        
        try:
            while True:
                try:
                    user_input = input("> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # 处理命令
                    if user_input.startswith("/"):
                        self._handle_command(user_input)
                        continue
                    
                    # 普通文本输入
                    if not self.is_processing:
                        self._submit_task(user_input)
                    else:
                        print("[System] Please wait, processing...")
                
                except KeyboardInterrupt:
                    print("\n[Interrupted]")
                    self.interrupt()
        
        except EOFError:
            pass
        finally:
            self.stop_voice()
            print("\nGoodbye!")
    
    def _handle_command(self, cmd: str):
        """处理命令"""
        parts = cmd.lower().split()
        command = parts[0]
        
        if command == "/voice":
            if len(parts) > 1:
                if parts[1] == "on":
                    self.enable_voice_input = True
                    self.start_voice()
                    print("[Voice] Voice input enabled")
                elif parts[1] == "off":
                    self.enable_voice_input = False
                    self.stop_voice()
                    print("[Voice] Voice input disabled")
        
        elif command == "/speak":
            if len(parts) > 1:
                if parts[1] == "on":
                    self.enable_tts = True
                    print("[Voice] Text-to-speech enabled")
                elif parts[1] == "off":
                    self.enable_tts = False
                    print("[Voice] Text-to-speech disabled")
        
        elif command == "/wake":
            if len(parts) > 1:
                new_wake = " ".join(parts[1:])
                self.set_wake_word(new_wake)
                print(f"[Voice] Wake word changed to: '{new_wake}'")
        
        elif command == "/interrupt":
            self.interrupt()
            print("[Voice] Interrupted")
        
        elif command == "/status":
            status = self.get_status()
            for key, value in status.items():
                print(f"  {key}: {value}")
        
        elif command == "/quit":
            raise SystemExit
        
        else:
            print(f"[Voice] Unknown command: {command}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice-Enabled GenericAgent")
    parser.add_argument("--wake-word", default="你好助手", help="Wake word")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice input")
    parser.add_argument("--no-tts", action="store_true", help="Disable text-to-speech")
    parser.add_argument("--llm-no", type=int, default=0, help="LLM backend number")
    
    args = parser.parse_args()
    
    # 创建Agent
    agent = GeneraticAgent()
    agent.llm_no = args.llm_no
    agent.verbose = False
    
    # 创建语音增强Agent
    voice_agent = VoiceEnabledAgent(
        agent=agent,
        wake_word=args.wake_word,
        enable_tts=not args.no_tts,
        enable_voice_input=not args.no_voice,
        auto_start_voice=not args.no_voice
    )
    
    # 运行CLI
    voice_agent.run_cli()


if __name__ == "__main__":
    main()
