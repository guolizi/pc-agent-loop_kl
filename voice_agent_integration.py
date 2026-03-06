"""
Voice Agent Integration - 语音Agent集成模块
将语音控制与GenericAgent无缝集成
"""

import os
import sys
import time
import queue
import threading
import re
from typing import Optional, Callable

# 导入Agent
from agentmain import GeneraticAgent

# 尝试导入语音模块
try:
    from voice_simple import SimpleVoiceController, VoiceConfig
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("Warning: voice_simple module not available")


class VoiceAgent:
    """
    语音增强型Agent
    支持语音唤醒、语音识别、语音合成
    """
    
    def __init__(
        self,
        agent: Optional[GeneraticAgent] = None,
        wake_word: str = "你好",
        enable_voice: bool = True,
        enable_tts: bool = True
    ):
        """
        初始化
        
        Args:
            agent: GenericAgent实例
            wake_word: 唤醒词
            enable_voice: 是否启用语音输入
            enable_tts: 是否启用语音合成
        """
        self.agent = agent or GeneraticAgent()
        self.wake_word = wake_word
        self.enable_voice = enable_voice
        self.enable_tts = enable_tts
        
        # 语音控制器
        self.voice: Optional[SimpleVoiceController] = None
        
        # 状态
        self.is_voice_active = False
        self.is_processing = False
        self.current_task_queue: Optional[queue.Queue] = None
        
        # 回调
        self.on_text_input: Optional[Callable[[str], None]] = None
        self.on_agent_response: Optional[Callable[[str], None]] = None
        
        # 初始化语音
        if enable_voice and VOICE_AVAILABLE:
            self._init_voice()
    
    def _init_voice(self):
        """初始化语音控制"""
        try:
            config = VoiceConfig(
                wake_word=self.wake_word,
                enable_interrupt=True
            )
            
            self.voice = SimpleVoiceController(config)
            
            # 设置回调
            self.voice.on_wake = self._on_wake
            self.voice.on_speech = self._on_speech
            self.voice.on_interrupt = self._on_interrupt
            
            print(f"[Voice] Initialized with wake word: '{self.wake_word}'")
            
        except Exception as e:
            print(f"[Voice] Initialization failed: {e}")
            self.voice = None
    
    def _on_wake(self):
        """唤醒回调"""
        print(f"\n[Voice] Wake word detected! Listening...")
    
    def _on_speech(self, text: str):
        """语音识别回调"""
        print(f"[Voice] Recognized: {text}")
        
        # 调用外部回调
        if self.on_text_input:
            self.on_text_input(text)
        
        # 提交给Agent处理
        self._submit_task(text)
    
    def _on_interrupt(self):
        """打断回调"""
        print("[Voice] Interrupted!")
        self.agent.abort()
        self.is_processing = False
    
    def _submit_task(self, query: str):
        """提交任务给Agent"""
        if self.is_processing:
            print("[Voice] Already processing, please wait...")
            if self.enable_tts and self.voice:
                self.voice.speak("请稍等，我正在处理中", block=False)
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
            
            while True:
                try:
                    item = self.current_task_queue.get(timeout=120)
                    
                    if 'next' in item:
                        # 流式输出
                        full_response = item['next']
                        print(f"\r[Agent] {full_response[-100:]}", end='', flush=True)
                    
                    if 'done' in item:
                        # 完成
                        full_response = item['done']
                        print(f"\n[Agent] {full_response}")
                        
                        # 语音合成
                        if self.enable_tts and self.voice:
                            clean_text = self._clean_for_speech(full_response)
                            if clean_text:
                                self.voice.speak(clean_text, block=False)
                        
                        # 回调
                        if self.on_agent_response:
                            self.on_agent_response(full_response)
                        
                        break
                
                except queue.Empty:
                    print("\n[Voice] Task timeout")
                    break
        
        except Exception as e:
            print(f"\n[Voice] Error: {e}")
        
        finally:
            self.is_processing = False
            self.current_task_queue = None
    
    def _clean_for_speech(self, text: str) -> str:
        """清理文本以便语音合成"""
        # 移除代码块
        text = re.sub(r'```[\s\S]*?```', ' [代码] ', text)
        text = re.sub(r'`[^`]*`', ' [代码] ', text)
        
        # 移除URL
        text = re.sub(r'https?://\S+', ' [链接] ', text)
        
        # 移除markdown标记
        text = re.sub(r'[#*_\[\](){}]', ' ', text)
        
        # 合并空白
        text = re.sub(r'\s+', ' ', text)
        
        # 限制长度
        if len(text) > 500:
            text = text[:500] + " ... [内容过长，已截断]"
        
        return text.strip()
    
    def start_voice(self) -> bool:
        """启动语音监听"""
        if not self.voice:
            print("[Voice] Voice control not available")
            return False
        
        if not self.voice.is_ready():
            print("[Voice] Voice controller not ready")
            return False
        
        if self.is_voice_active:
            return True
        
        self.voice.start()
        self.is_voice_active = True
        print(f"[Voice] Started. Say '{self.wake_word}' to wake up.")
        return True
    
    def stop_voice(self):
        """停止语音监听"""
        if self.voice:
            self.voice.stop()
        self.is_voice_active = False
    
    def speak(self, text: str, block: bool = False):
        """语音合成"""
        if self.voice:
            self.voice.speak(text, block)
    
    def interrupt(self):
        """打断"""
        if self.voice:
            self.voice.stop()
        self.agent.abort()
        self.is_processing = False
    
    def text_input(self, text: str):
        """文本输入（非语音）"""
        print(f"[Text] {text}")
        self._submit_task(text)
    
    def run(self):
        """运行主循环"""
        # 启动Agent后台线程
        threading.Thread(target=self.agent.run, daemon=True).start()
        
        # 启动语音
        if self.enable_voice:
            self.start_voice()
        
        print("\n" + "="*60)
        print("Voice-Enabled GenericAgent")
        print("="*60)
        print(f"Wake word: '{self.wake_word}'")
        print("Commands:")
        print("  /voice on/off  - Toggle voice input")
        print("  /speak on/off  - Toggle text-to-speech")
        print("  /wake <word>   - Change wake word")
        print("  /interrupt     - Interrupt current task")
        print("  /quit          - Exit")
        print("="*60 + "\n")
        
        try:
            while True:
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                
                # 处理命令
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue
                
                # 文本输入
                self.text_input(user_input)
        
        except KeyboardInterrupt:
            print("\n[Interrupted]")
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
                    self.enable_voice = True
                    self.start_voice()
                    print("[Voice] Voice input enabled")
                elif parts[1] == "off":
                    self.enable_voice = False
                    self.stop_voice()
                    print("[Voice] Voice input disabled")
        
        elif command == "/speak":
            if len(parts) > 1:
                self.enable_tts = (parts[1] == "on")
                print(f"[Voice] Text-to-speech {'enabled' if self.enable_tts else 'disabled'}")
        
        elif command == "/wake":
            if len(parts) > 1:
                self.wake_word = " ".join(parts[1:])
                if self.voice:
                    self.voice.config.wake_word = self.wake_word
                print(f"[Voice] Wake word changed to: '{self.wake_word}'")
        
        elif command == "/interrupt":
            self.interrupt()
            print("[Voice] Interrupted")
        
        elif command == "/quit":
            raise SystemExit
        
        else:
            print(f"[Voice] Unknown command: {command}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice-Enabled GenericAgent")
    parser.add_argument("--wake-word", default="你好", help="Wake word")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice input")
    parser.add_argument("--no-tts", action="store_true", help="Disable text-to-speech")
    parser.add_argument("--llm-no", type=int, default=0, help="LLM backend number")
    
    args = parser.parse_args()
    
    # 创建Agent
    agent = GeneraticAgent()
    agent.llm_no = args.llm_no
    agent.verbose = False
    
    # 创建语音Agent
    voice_agent = VoiceAgent(
        agent=agent,
        wake_word=args.wake_word,
        enable_voice=not args.no_voice,
        enable_tts=not args.no_tts
    )
    
    # 运行
    voice_agent.run()


if __name__ == "__main__":
    main()
