"""
Voice Control Module for GenericAgent
提供离线语音识别、语音合成、唤醒词检测和实时语音交互功能
"""

import os
import sys
import json
import time
import wave
import queue
import threading
import tempfile
import numpy as np
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

# 音频处理
import sounddevice as sd
import soundfile as sf
from collections import deque

# 配置日志
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """语音控制配置"""
    # 唤醒词配置
    wake_word: str = "你好助手"
    wake_word_sensitivity: float = 0.5
    
    # 音频输入配置
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 0.5  # 每次读取音频的时长（秒）
    
    # VAD (Voice Activity Detection) 配置
    vad_aggressiveness: int = 2  # 0-3, 越高越严格
    vad_frame_duration: int = 30  # 10, 20, or 30 ms
    silence_timeout: float = 2.0  # 静音超时（秒）
    
    # TTS 配置
    tts_rate: int = 150  # 语速
    tts_volume: float = 1.0  # 音量 0.0-1.0
    tts_voice_id: Optional[str] = None  # 音色ID
    
    # 模型路径
    vosk_model_path: Optional[str] = None  # Vosk模型路径
    piper_model_path: Optional[str] = None  # Piper TTS模型路径
    
    # 打断配置
    enable_interrupt: bool = True
    interrupt_wake_words: List[str] = field(default_factory=lambda: ["停", "停止", "等一下", "打断"])


class AudioBuffer:
    """音频缓冲区，用于管理音频数据流"""
    
    def __init__(self, max_seconds: float = 10.0, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.max_samples = int(max_seconds * sample_rate)
        self.buffer = deque(maxlen=self.max_samples)
        self.lock = threading.Lock()
    
    def extend(self, data: np.ndarray):
        """添加音频数据到缓冲区"""
        with self.lock:
            self.buffer.extend(data)
    
    def get(self) -> np.ndarray:
        """获取当前缓冲区的所有数据"""
        with self.lock:
            return np.array(self.buffer)
    
    def clear(self):
        """清空缓冲区"""
        with self.lock:
            self.buffer.clear()
    
    def __len__(self):
        with self.lock:
            return len(self.buffer)


class VADProcessor:
    """语音活动检测处理器"""
    
    def __init__(self, aggressiveness: int = 2, frame_duration: int = 30, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.frame_duration = frame_duration
        self.frame_size = int(sample_rate * frame_duration / 1000)
        
        # 尝试使用 webrtcvad
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
            self.has_vad = True
        except ImportError:
            logger.warning("webrtcvad not installed, using simple energy-based VAD")
            self.has_vad = False
            self.energy_threshold = 0.01
    
    def is_speech(self, audio_frame: bytes) -> bool:
        """检测音频帧是否包含语音"""
        if self.has_vad:
            try:
                import webrtcvad
                return self.vad.is_speech(audio_frame, self.sample_rate)
            except:
                return self._energy_based_vad(audio_frame)
        else:
            return self._energy_based_vad(audio_frame)
    
    def _energy_based_vad(self, audio_frame: bytes) -> bool:
        """基于能量的简单VAD"""
        audio_array = np.frombuffer(audio_frame, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        return energy > self.energy_threshold * 32767


class SpeechRecognizer:
    """离线语音识别器 (基于 Vosk)"""
    
    def __init__(self, model_path: Optional[str] = None, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.model_path = model_path
        self.model = None
        self.recognizer = None
        self._init_model()
    
    def _init_model(self):
        """初始化 Vosk 模型"""
        try:
            from vosk import Model, KaldiRecognizer
            
            # 如果未指定模型路径，尝试查找默认路径
            if self.model_path is None:
                possible_paths = [
                    "vosk-model-small-cn-0.22",
                    "vosk-model-cn-0.22",
                    "models/vosk-model-small-cn-0.22",
                    "models/vosk-model-cn-0.22",
                    os.path.expanduser("~/.local/share/vosk/vosk-model-small-cn-0.22"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        self.model_path = path
                        break
            
            if self.model_path and os.path.exists(self.model_path):
                logger.info(f"Loading Vosk model from: {self.model_path}")
                self.model = Model(self.model_path)
                self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
                logger.info("Vosk model loaded successfully")
            else:
                logger.error("Vosk model not found. Please download a model from https://alphacephei.com/vosk/models")
                
        except ImportError:
            logger.error("vosk not installed. Please install: pip install vosk")
        except Exception as e:
            logger.error(f"Error loading Vosk model: {e}")
    
    def is_ready(self) -> bool:
        """检查识别器是否已准备好"""
        return self.model is not None and self.recognizer is not None
    
    def recognize_chunk(self, audio_data: np.ndarray) -> Optional[str]:
        """识别音频块，返回部分结果或None"""
        if not self.is_ready():
            return None
        
        # 转换为 int16 bytes
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        audio_bytes = audio_data.tobytes()
        
        if self.recognizer.AcceptWaveform(audio_bytes):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        return None
    
    def get_partial(self) -> str:
        """获取部分识别结果"""
        if not self.is_ready():
            return ""
        
        partial = json.loads(self.recognizer.PartialResult())
        return partial.get("partial", "")
    
    def finalize(self) -> str:
        """获取最终识别结果并重置"""
        if not self.is_ready():
            return ""
        
        result = json.loads(self.recognizer.FinalResult())
        text = result.get("text", "")
        
        # 重置识别器
        self.recognizer = self.model.NewRecognizer(self.sample_rate)
        
        return text
    
    def reset(self):
        """重置识别器状态"""
        if self.is_ready():
            self.recognizer = self.model.NewRecognizer(self.sample_rate)


class TextToSpeech:
    """文本转语音 (支持多种后端)"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.backend = None
        self.speaking = False
        self.interrupt_flag = threading.Event()
        self._init_backend()
    
    def _init_backend(self):
        """初始化 TTS 后端"""
        # 优先尝试 pyttsx3 (离线，支持Windows/Mac/Linux)
        try:
            import pyttsx3
            self.backend = pyttsx3.init()
            self.backend.setProperty('rate', self.config.tts_rate)
            self.backend.setProperty('volume', self.config.tts_volume)
            
            # 设置音色
            if self.config.tts_voice_id:
                self.backend.setProperty('voice', self.config.tts_voice_id)
            
            self.backend_type = "pyttsx3"
            logger.info("TTS backend: pyttsx3")
            return
        except ImportError:
            pass
        
        # 尝试 Piper (高质量离线TTS)
        if self.config.piper_model_path and os.path.exists(self.config.piper_model_path):
            try:
                # Piper 通过命令行调用
                self.backend_type = "piper"
                logger.info("TTS backend: piper")
                return
            except Exception as e:
                logger.error(f"Piper init error: {e}")
        
        # 尝试 edge-tts (在线，但质量高)
        try:
            import edge_tts
            self.backend_type = "edge"
            logger.info("TTS backend: edge-tts")
            return
        except ImportError:
            pass
        
        logger.error("No TTS backend available. Please install pyttsx3, piper-tts, or edge-tts")
    
    def is_ready(self) -> bool:
        """检查TTS是否可用"""
        return self.backend_type is not None
    
    def speak(self, text: str, block: bool = False) -> bool:
        """
        合成并播放语音
        
        Args:
            text: 要合成的文本
            block: 是否阻塞等待播放完成
        
        Returns:
            是否成功开始播放
        """
        if not self.is_ready() or not text:
            return False
        
        # 清除打断标志
        self.interrupt_flag.clear()
        
        if self.backend_type == "pyttsx3":
            return self._speak_pyttsx3(text, block)
        elif self.backend_type == "piper":
            return self._speak_piper(text, block)
        elif self.backend_type == "edge":
            return self._speak_edge(text, block)
        
        return False
    
    def _speak_pyttsx3(self, text: str, block: bool) -> bool:
        """使用 pyttsx3 播放"""
        try:
            self.backend.say(text)
            if block:
                self.backend.runAndWait()
            else:
                threading.Thread(target=self.backend.runAndWait, daemon=True).start()
            return True
        except Exception as e:
            logger.error(f"pyttsx3 speak error: {e}")
            return False
    
    def _speak_piper(self, text: str, block: bool) -> bool:
        """使用 Piper 播放"""
        def play():
            try:
                import subprocess
                
                # 生成临时音频文件
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    wav_path = f.name
                
                # 调用 piper 生成音频
                cmd = [
                    "piper",
                    "--model", self.config.piper_model_path,
                    "--output_file", wav_path
                ]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                proc.communicate(input=text)
                proc.wait()
                
                # 播放音频
                if os.path.exists(wav_path):
                    data, samplerate = sf.read(wav_path)
                    sd.play(data, samplerate)
                    sd.wait()
                    os.remove(wav_path)
                    
            except Exception as e:
                logger.error(f"Piper speak error: {e}")
        
        if block:
            play()
        else:
            threading.Thread(target=play, daemon=True).start()
        return True
    
    def _speak_edge(self, text: str, block: bool) -> bool:
        """使用 edge-tts 播放"""
        async def _play_async():
            try:
                import edge_tts
                import asyncio
                
                communicate = edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural")
                
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    mp3_path = f.name
                
                await communicate.save(mp3_path)
                
                # 播放
                data, samplerate = sf.read(mp3_path)
                sd.play(data, samplerate)
                sd.wait()
                os.remove(mp3_path)
                
            except Exception as e:
                logger.error(f"Edge TTS error: {e}")
        
        def play():
            import asyncio
            asyncio.run(_play_async())
        
        if block:
            play()
        else:
            threading.Thread(target=play, daemon=True).start()
        return True
    
    def interrupt(self):
        """打断当前播放"""
        self.interrupt_flag.set()
        sd.stop()
        self.speaking = False
    
    def set_voice(self, voice_id: str):
        """设置音色"""
        self.config.tts_voice_id = voice_id
        if self.backend_type == "pyttsx3":
            self.backend.setProperty('voice', voice_id)
    
    def set_rate(self, rate: int):
        """设置语速"""
        self.config.tts_rate = rate
        if self.backend_type == "pyttsx3":
            self.backend.setProperty('rate', rate)
    
    def set_volume(self, volume: float):
        """设置音量"""
        self.config.tts_volume = volume
        if self.backend_type == "pyttsx3":
            self.backend.setProperty('volume', volume)
    
    def list_voices(self) -> List[Dict[str, str]]:
        """列出可用音色"""
        voices = []
        if self.backend_type == "pyttsx3":
            for voice in self.backend.getProperty('voices'):
                voices.append({
                    'id': voice.id,
                    'name': voice.name,
                    'languages': voice.languages if hasattr(voice, 'languages') else []
                })
        return voices


class WakeWordDetector:
    """唤醒词检测器"""
    
    def __init__(self, wake_words: List[str], sensitivity: float = 0.5):
        self.wake_words = [w.lower() for w in wake_words]
        self.sensitivity = sensitivity
        self.detected = threading.Event()
    
    def check(self, text: str) -> bool:
        """检查文本是否包含唤醒词"""
        text_lower = text.lower()
        for wake_word in self.wake_words:
            if wake_word in text_lower:
                return True
        return False
    
    def check_interrupt(self, text: str, interrupt_words: List[str]) -> bool:
        """检查是否是打断词"""
        text_lower = text.lower()
        for word in interrupt_words:
            if word in text_lower:
                return True
        return False


class VoiceController:
    """
    语音控制器主类
    整合语音识别、语音合成、唤醒词检测和音频管理
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        # 组件
        self.recognizer: Optional[SpeechRecognizer] = None
        self.tts: Optional[TextToSpeech] = None
        self.vad: Optional[VADProcessor] = None
        self.wake_detector: Optional[WakeWordDetector] = None
        
        # 状态
        self.is_listening = False
        self.is_speaking = False
        self.is_awake = False  # 是否已被唤醒
        self.audio_queue = queue.Queue()
        
        # 回调
        self.on_wake_word: Optional[Callable] = None
        self.on_speech_recognized: Optional[Callable[[str], None]] = None
        self.on_interrupt: Optional[Callable] = None
        
        # 线程控制
        self._stop_event = threading.Event()
        self._listen_thread: Optional[threading.Thread] = None
        
        # 音频流
        self._audio_stream = None
        
        self._init_components()
    
    def _init_components(self):
        """初始化所有组件"""
        # 初始化语音识别
        self.recognizer = SpeechRecognizer(
            model_path=self.config.vosk_model_path,
            sample_rate=self.config.sample_rate
        )
        
        # 初始化TTS
        self.tts = TextToSpeech(self.config)
        
        # 初始化VAD
        self.vad = VADProcessor(
            aggressiveness=self.config.vad_aggressiveness,
            frame_duration=self.config.vad_frame_duration,
            sample_rate=self.config.sample_rate
        )
        
        # 初始化唤醒词检测
        self.wake_detector = WakeWordDetector(
            wake_words=[self.config.wake_word],
            sensitivity=self.config.wake_word_sensitivity
        )
        
        logger.info("VoiceController initialized")
    
    def start(self):
        """启动语音控制"""
        if self.is_listening:
            return
        
        self._stop_event.clear()
        self.is_listening = True
        
        # 启动音频捕获线程
        self._listen_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self._listen_thread.start()
        
        logger.info("VoiceController started")
    
    def stop(self):
        """停止语音控制"""
        self._stop_event.set()
        self.is_listening = False
        
        if self._audio_stream:
            self._audio_stream.stop()
            self._audio_stream.close()
        
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
        
        logger.info("VoiceController stopped")
    
    def _audio_capture_loop(self):
        """音频捕获和处理循环"""
        logger.info("Audio capture loop started")
        
        # 音频缓冲区
        buffer = AudioBuffer(max_seconds=5.0, sample_rate=self.config.sample_rate)
        
        # 状态机
        state = "WAITING_WAKE"  # WAITING_WAKE, LISTENING, PROCESSING
        silence_start = None
        
        def audio_callback(indata, frames, time_info, status):
            """音频回调函数"""
            if status:
                logger.warning(f"Audio status: {status}")
            
            # 将音频数据放入队列
            audio_data = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
            self.audio_queue.put(audio_data.copy())
        
        # 启动音频流
        try:
            self._audio_stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=np.float32,
                blocksize=int(self.config.sample_rate * self.config.chunk_duration),
                callback=audio_callback
            )
            self._audio_stream.start()
            
            while not self._stop_event.is_set():
                try:
                    # 从队列获取音频数据
                    audio_data = self.audio_queue.get(timeout=0.1)
                    buffer.extend(audio_data)
                    
                    # 状态机处理
                    if state == "WAITING_WAKE":
                        state = self._handle_waiting_wake(buffer)
                    
                    elif state == "LISTENING":
                        state, silence_start = self._handle_listening(buffer, silence_start)
                    
                    elif state == "PROCESSING":
                        state = self._handle_processing(buffer)
                        silence_start = None
                
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
        
        except Exception as e:
            logger.error(f"Audio stream error: {e}")
        finally:
            if self._audio_stream:
                self._audio_stream.stop()
                self._audio_stream.close()
    
    def _handle_waiting_wake(self, buffer: AudioBuffer) -> str:
        """处理等待唤醒状态"""
        # 获取音频数据进行识别
        audio_data = buffer.get()
        
        if len(audio_data) < self.config.sample_rate * 0.5:  # 至少0.5秒
            return "WAITING_WAKE"
        
        # 尝试识别
        text = self.recognizer.recognize_chunk(audio_data)
        
        if text:
            logger.info(f"Heard: {text}")
            
            # 检查是否是打断词
            if self.config.enable_interrupt and self.is_speaking:
                if self.wake_detector.check_interrupt(text, self.config.interrupt_wake_words):
                    logger.info("Interrupt detected!")
                    self.interrupt()
                    if self.on_interrupt:
                        self.on_interrupt()
                    buffer.clear()
                    self.recognizer.reset()
                    return "WAITING_WAKE"
            
            # 检查唤醒词
            if self.wake_detector.check(text):
                logger.info("Wake word detected!")
                self.is_awake = True
                buffer.clear()
                self.recognizer.reset()
                
                if self.on_wake_word:
                    self.on_wake_word()
                
                # 播放提示音
                if self.tts.is_ready():
                    self.tts.speak("我在听", block=False)
                
                return "LISTENING"
            
            # 清空旧数据，保留最近1秒
            buffer.clear()
        
        return "WAITING_WAKE"
    
    def _handle_listening(self, buffer: AudioBuffer, silence_start: Optional[float]) -> tuple:
        """处理监听状态"""
        audio_data = buffer.get()
        
        # 检查静音
        is_speech = False
        if len(audio_data) >= self.vad.frame_size:
            # 取最后一帧进行VAD检测
            last_frame = audio_data[-self.vad.frame_size:]
            if last_frame.dtype != np.int16:
                last_frame = (last_frame * 32767).astype(np.int16)
            is_speech = self.vad.is_speech(last_frame.tobytes())
        
        if not is_speech:
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start > self.config.silence_timeout:
                # 静音超时，进入处理状态
                logger.info("Silence timeout, processing speech...")
                return "PROCESSING", silence_start
        else:
            silence_start = None
        
        return "LISTENING", silence_start
    
    def _handle_processing(self, buffer: AudioBuffer) -> str:
        """处理语音识别"""
        audio_data = buffer.get()
        
        if len(audio_data) > 0:
            # 最终识别
            text = self.recognizer.finalize()
            
            if text:
                logger.info(f"Recognized: {text}")
                
                if self.on_speech_recognized:
                    self.on_speech_recognized(text)
            
            buffer.clear()
        
        self.is_awake = False
        return "WAITING_WAKE"
    
    def speak(self, text: str, block: bool = False) -> bool:
        """
        语音合成并播放
        
        Args:
            text: 要合成的文本
            block: 是否阻塞等待播放完成
        
        Returns:
            是否成功
        """
        if not self.tts or not self.tts.is_ready():
            return False
        
        self.is_speaking = True
        
        def on_complete():
            self.is_speaking = False
        
        if block:
            result = self.tts.speak(text, block=True)
            on_complete()
            return result
        else:
            def speak_thread():
                self.tts.speak(text, block=True)
                on_complete()
            
            threading.Thread(target=speak_thread, daemon=True).start()
            return True
    
    def interrupt(self):
        """打断当前语音播放"""
        if self.tts:
            self.tts.interrupt()
        self.is_speaking = False
    
    def is_ready(self) -> bool:
        """检查语音控制器是否就绪"""
        return (
            self.recognizer is not None and 
            self.recognizer.is_ready() and
            self.tts is not None and
            self.tts.is_ready()
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "is_listening": self.is_listening,
            "is_speaking": self.is_speaking,
            "is_awake": self.is_awake,
            "recognizer_ready": self.recognizer.is_ready() if self.recognizer else False,
            "tts_ready": self.tts.is_ready() if self.tts else False,
        }


# 便捷函数
def create_default_voice_controller(
    wake_word: str = "你好助手",
    on_speech_recognized: Optional[Callable[[str], None]] = None
) -> VoiceController:
    """
    创建默认配置的语音控制器
    
    Args:
        wake_word: 唤醒词
        on_speech_recognized: 语音识别回调函数
    
    Returns:
        VoiceController实例
    """
    config = VoiceConfig(wake_word=wake_word)
    controller = VoiceController(config)
    
    if on_speech_recognized:
        controller.on_speech_recognized = on_speech_recognized
    
    return controller


if __name__ == "__main__":
    # 测试代码
    print("Voice Control Module Test")
    print("=" * 50)
    
    def on_wake():
        print("[Wake Word Detected]")
    
    def on_speech(text):
        print(f"[Speech Recognized]: {text}")
    
    def on_interrupt():
        print("[Interrupted]")
    
    # 创建控制器
    controller = VoiceController()
    controller.on_wake_word = on_wake
    controller.on_speech_recognized = on_speech
    controller.on_interrupt = on_interrupt
    
    # 检查状态
    status = controller.get_status()
    print(f"Status: {status}")
    
    if controller.is_ready():
        print("\nVoice controller is ready!")
        print(f"Say '{controller.config.wake_word}' to wake me up")
        print("Say '停' or '停止' to interrupt")
        print("Press Ctrl+C to exit\n")
        
        controller.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            controller.stop()
    else:
        print("\nVoice controller is not ready.")
        print("Please install required dependencies:")
        print("  pip install vosk sounddevice soundfile numpy")
        print("  pip install pyttsx3  # or piper-tts / edge-tts")
        print("\nAnd download Vosk model:")
        print("  wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip")
