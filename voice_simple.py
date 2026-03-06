"""
Simplified Voice Control Module for GenericAgent
简化版语音控制模块，减少依赖，提高兼容性
"""

import os
import sys
import time
import wave
import queue
import threading
import tempfile
import subprocess
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# 尝试导入音频库
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: numpy not available")

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("Warning: sounddevice not available")

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False


@dataclass
class VoiceConfig:
    """语音配置"""
    wake_word: str = "你好助手"
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 0.5
    silence_timeout: float = 2.0
    tts_rate: int = 150
    tts_volume: float = 1.0
    enable_interrupt: bool = True
    interrupt_words: List[str] = None
    
    def __post_init__(self):
        if self.interrupt_words is None:
            self.interrupt_words = ["停", "停止", "等一下", "打断", "别说了"]


class SimpleRecorder:
    """简单录音器"""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.audio_buffer = []
        self._stream = None
    
    def start_recording(self):
        """开始录音"""
        if not SOUNDDEVICE_AVAILABLE:
            print("Error: sounddevice not available")
            return False
        
        self.is_recording = True
        self.audio_buffer = []
        
        def callback(indata, frames, time_info, status):
            if self.is_recording:
                self.audio_buffer.append(indata.copy())
        
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=callback
            )
            self._stream.start()
            return True
        except Exception as e:
            print(f"Recording error: {e}")
            return False
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """停止录音并返回音频数据"""
        self.is_recording = False
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        if self.audio_buffer and NUMPY_AVAILABLE:
            return np.concatenate(self.audio_buffer, axis=0)
        return None
    
    def save_to_file(self, audio_data: np.ndarray, filepath: str):
        """保存音频到文件"""
        if not SOUNDFILE_AVAILABLE:
            print("Error: soundfile not available")
            return False
        
        try:
            sf.write(filepath, audio_data, self.sample_rate)
            return True
        except Exception as e:
            print(f"Save error: {e}")
            return False


class SimpleRecognizer:
    """简单语音识别器（支持多种后端）"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.backend = None
        self._init_backend()
    
    def _init_backend(self):
        """初始化识别后端"""
        # 尝试 Vosk
        try:
            from vosk import Model, KaldiRecognizer
            
            # 查找模型
            model_paths = [
                "vosk-model-small-cn-0.22",
                "models/vosk-model-small-cn-0.22",
                os.path.expanduser("~/.local/share/vosk/vosk-model-small-cn-0.22"),
            ]
            
            for path in model_paths:
                if os.path.exists(path):
                    self.model = Model(path)
                    self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
                    self.backend = "vosk"
                    print(f"Using Vosk for speech recognition (model: {path})")
                    return
            
            print("Vosk model not found. Please download from https://alphacephei.com/vosk/models")
        except ImportError:
            pass
        
        # 尝试 Whisper
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")
            self.backend = "whisper"
            print("Using Whisper for speech recognition")
            return
        except ImportError:
            pass
        
        # 尝试使用系统命令（如 Windows 的语音识别）
        if os.name == 'nt':
            self.backend = "system"
            print("Using system speech recognition")
        else:
            print("No speech recognition backend available")
    
    def is_ready(self) -> bool:
        return self.backend is not None
    
    def recognize(self, audio_data: np.ndarray) -> str:
        """识别音频"""
        if not self.is_ready():
            return ""
        
        if self.backend == "vosk":
            return self._recognize_vosk(audio_data)
        elif self.backend == "whisper":
            return self._recognize_whisper(audio_data)
        elif self.backend == "system":
            return self._recognize_system(audio_data)
        
        return ""
    
    def _recognize_vosk(self, audio_data: np.ndarray) -> str:
        """使用 Vosk 识别"""
        try:
            # 转换为 int16
            if audio_data.dtype != np.int16:
                audio_data = (audio_data * 32767).astype(np.int16)
            
            audio_bytes = audio_data.tobytes()
            
            if self.recognizer.AcceptWaveform(audio_bytes):
                import json
                result = json.loads(self.recognizer.Result())
                return result.get("text", "")
            
            return ""
        except Exception as e:
            print(f"Vosk recognition error: {e}")
            return ""
    
    def _recognize_whisper(self, audio_data: np.ndarray) -> str:
        """使用 Whisper 识别"""
        try:
            # 保存临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            
            import soundfile as sf
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 识别
            result = self.whisper_model.transcribe(temp_path, language="zh")
            
            # 清理
            os.remove(temp_path)
            
            return result.get("text", "")
        except Exception as e:
            print(f"Whisper recognition error: {e}")
            return ""
    
    def _recognize_system(self, audio_data: np.ndarray) -> str:
        """使用系统语音识别（Windows）"""
        try:
            # 保存临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            
            import soundfile as sf
            sf.write(temp_path, audio_data, self.sample_rate)
            
            # 使用 PowerShell 调用 Windows 语音识别
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
            $recognizer.SetInputToWaveFile("{temp_path}")
            $result = $recognizer.Recognize()
            if ($result) {{ $result.Text }} else {{ "" }}
            '''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True
            )
            
            os.remove(temp_path)
            
            return result.stdout.strip()
        except Exception as e:
            print(f"System recognition error: {e}")
            return ""


class SimpleTTS:
    """简单文本转语音"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.backend = None
        self.speaking = False
        self._init_backend()
    
    def _init_backend(self):
        """初始化 TTS 后端"""
        # 尝试 pyttsx3
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', self.config.tts_rate)
            self.engine.setProperty('volume', self.config.tts_volume)
            self.backend = "pyttsx3"
            print("Using pyttsx3 for text-to-speech")
            return
        except ImportError:
            pass
        
        # 尝试 edge-tts
        try:
            import edge_tts
            self.backend = "edge"
            print("Using edge-tts for text-to-speech")
            return
        except ImportError:
            pass
        
        # Windows 系统语音
        if os.name == 'nt':
            self.backend = "system"
            print("Using Windows system speech")
        else:
            print("No TTS backend available")
    
    def is_ready(self) -> bool:
        return self.backend is not None
    
    def speak(self, text: str, block: bool = False):
        """合成并播放语音"""
        if not self.is_ready() or not text:
            return False
        
        if self.backend == "pyttsx3":
            return self._speak_pyttsx3(text, block)
        elif self.backend == "edge":
            return self._speak_edge(text, block)
        elif self.backend == "system":
            return self._speak_system(text, block)
        
        return False
    
    def _speak_pyttsx3(self, text: str, block: bool):
        """使用 pyttsx3"""
        try:
            self.engine.say(text)
            if block:
                self.engine.runAndWait()
            else:
                threading.Thread(target=self.engine.runAndWait, daemon=True).start()
            return True
        except Exception as e:
            print(f"pyttsx3 error: {e}")
            return False
    
    def _speak_edge(self, text: str, block: bool):
        """使用 edge-tts"""
        def play():
            try:
                import asyncio
                import edge_tts
                
                async def _speak():
                    communicate = edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural")
                    
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        mp3_path = f.name
                    
                    await communicate.save(mp3_path)
                    
                    # 播放
                    if SOUNDFILE_AVAILABLE and SOUNDDEVICE_AVAILABLE:
                        data, samplerate = sf.read(mp3_path)
                        sd.play(data, samplerate)
                        sd.wait()
                    
                    os.remove(mp3_path)
                
                asyncio.run(_speak())
            except Exception as e:
                print(f"edge-tts error: {e}")
        
        if block:
            play()
        else:
            threading.Thread(target=play, daemon=True).start()
        return True
    
    def _speak_system(self, text: str, block: bool):
        """使用 Windows 系统语音"""
        try:
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.Speak("{text}")
            '''
            
            if block:
                subprocess.run(["powershell", "-Command", ps_script])
            else:
                threading.Thread(
                    target=subprocess.run,
                    args=(["powershell", "-Command", ps_script],),
                    daemon=True
                ).start()
            return True
        except Exception as e:
            print(f"System TTS error: {e}")
            return False
    
    def stop(self):
        """停止播放"""
        if SOUNDDEVICE_AVAILABLE:
            sd.stop()
        self.speaking = False


class SimpleVoiceController:
    """简化版语音控制器"""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        self.recorder = SimpleRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels
        )
        self.recognizer = SimpleRecognizer(sample_rate=self.config.sample_rate)
        self.tts = SimpleTTS(self.config)
        
        self.is_running = False
        self.is_awake = False
        self._stop_event = threading.Event()
        
        # 回调
        self.on_wake: Optional[Callable] = None
        self.on_speech: Optional[Callable[[str], None]] = None
        self.on_interrupt: Optional[Callable] = None
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self.recognizer.is_ready() and self.tts.is_ready()
    
    def start(self):
        """启动语音控制"""
        if self.is_running:
            return
        
        if not self.is_ready():
            print("Voice controller not ready. Please check dependencies.")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # 启动监听线程
        threading.Thread(target=self._listen_loop, daemon=True).start()
        
        print(f"Voice controller started. Say '{self.config.wake_word}' to wake up.")
    
    def stop(self):
        """停止语音控制"""
        self._stop_event.set()
        self.is_running = False
        self.recorder.stop_recording()
        self.tts.stop()
        print("Voice controller stopped.")
    
    def _listen_loop(self):
        """监听循环"""
        while not self._stop_event.is_set():
            try:
                if not self.is_awake:
                    # 等待唤醒
                    self._wait_for_wake_word()
                else:
                    # 监听指令
                    self._listen_for_command()
            except Exception as e:
                print(f"Listen loop error: {e}")
                time.sleep(1)
    
    def _wait_for_wake_word(self):
        """等待唤醒词"""
        print(f"\n[Listening for wake word: '{self.config.wake_word}']")
        
        # 录制短音频
        if self.recorder.start_recording():
            time.sleep(2)  # 录制2秒
            audio = self.recorder.stop_recording()
            
            if audio is not None:
                text = self.recognizer.recognize(audio)
                print(f"  Heard: {text}")
                
                # 检查打断
                if self.config.enable_interrupt and self._check_interrupt(text):
                    self._handle_interrupt()
                    return
                
                # 检查唤醒词
                if self.config.wake_word in text:
                    self.is_awake = True
                    print(f"  [Wake word detected!]")
                    if self.on_wake:
                        self.on_wake()
                    self.tts.speak("我在听", block=False)
    
    def _listen_for_command(self):
        """监听指令"""
        print("\n[Listening for command...]")
        
        # 录制音频（带静音检测）
        if self.recorder.start_recording():
            silence_start = None
            max_duration = 10  # 最大录制10秒
            start_time = time.time()
            
            while time.time() - start_time < max_duration:
                time.sleep(0.1)
                
                # 简单静音检测（基于音频能量）
                if len(self.recorder.audio_buffer) > 10:
                    recent = np.concatenate(self.recorder.audio_buffer[-10:])
                    energy = np.sqrt(np.mean(recent ** 2))
                    
                    if energy < 0.01:  # 静音阈值
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > self.config.silence_timeout:
                            break
                    else:
                        silence_start = None
            
            audio = self.recorder.stop_recording()
            
            if audio is not None:
                text = self.recognizer.recognize(audio)
                print(f"  Command: {text}")
                
                # 检查打断
                if self.config.enable_interrupt and self._check_interrupt(text):
                    self._handle_interrupt()
                    self.is_awake = False
                    return
                
                # 处理指令
                if text.strip():
                    if self.on_speech:
                        self.on_speech(text)
                
                self.is_awake = False
    
    def _check_interrupt(self, text: str) -> bool:
        """检查是否是打断词"""
        for word in self.config.interrupt_words:
            if word in text:
                return True
        return False
    
    def _handle_interrupt(self):
        """处理打断"""
        print("  [Interrupted]")
        self.tts.stop()
        if self.on_interrupt:
            self.on_interrupt()
    
    def speak(self, text: str, block: bool = False):
        """语音合成"""
        return self.tts.speak(text, block)


def test_voice_control():
    """测试语音控制"""
    print("="*60)
    print("Voice Control Test")
    print("="*60)
    
    config = VoiceConfig()
    controller = SimpleVoiceController(config)
    
    if not controller.is_ready():
        print("\nVoice controller not ready.")
        print("Please install required packages:")
        print("  pip install vosk sounddevice soundfile numpy")
        print("  pip install pyttsx3")
        print("\nAnd download Vosk model:")
        print("  wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip")
        return
    
    def on_wake():
        print("[Callback] Wake word detected!")
    
    def on_speech(text):
        print(f"[Callback] Speech recognized: {text}")
        # 回显
        controller.speak(f"你说的是：{text}", block=False)
    
    def on_interrupt():
        print("[Callback] Interrupted!")
    
    controller.on_wake = on_wake
    controller.on_speech = on_speech
    controller.on_interrupt = on_interrupt
    
    controller.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.stop()


if __name__ == "__main__":
    test_voice_control()
