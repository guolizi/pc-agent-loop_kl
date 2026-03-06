# Voice Control for GenericAgent

## 功能特性

- 🎤 **实时语音监听**: 持续监听麦克风输入
- 🗣️ **自定义唤醒词**: 默认 "你好助手"，可自定义
- 💬 **实时语音输出**: Agent回复自动语音合成
- ⏹️ **随时打断**: 说 "停"、"停止"、"等一下" 等打断当前播放
- 🎨 **可调音色**: 支持调整语速、音量、音色
- 🔌 **离线支持**: 支持离线语音识别和合成

## 快速开始

### 1. 安装依赖

```bash
python setup_voice.py
```

或手动安装：
```bash
pip install sounddevice soundfile numpy pyttsx3 vosk
```

### 2. 下载语音模型

脚本会自动下载，或手动下载：
```bash
wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
unzip vosk-model-small-cn-0.22.zip
```

### 3. 启动

```bash
# Windows
start_voice.bat

# 或
python voice_agent_integration.py

# 自定义唤醒词
python voice_agent_integration.py --wake-word "小助手"
```

## 使用方法

### 语音交互

1. 说唤醒词 "你好助手"（或自定义）
2. 听到 "我在听" 提示音后，说出你的指令
3. Agent会自动处理并通过语音回复
4. 可以随时说 "停" 或 "停止" 打断

### 命令

在命令行中输入：

- `/voice on/off` - 开启/关闭语音输入
- `/speak on/off` - 开启/关闭语音合成
- `/wake <词>` - 更改唤醒词
- `/interrupt` - 打断当前任务
- `/quit` - 退出

### 程序内使用

```python
from voice_agent_integration import VoiceAgent

# 创建语音Agent
agent = VoiceAgent(wake_word="你好助手")

# 启动
agent.run()
```

## 配置

### 调整TTS设置

```python
# 设置语速（默认150）
agent.voice.voice.tts.set_rate(200)

# 设置音量（0.0-1.0）
agent.voice.voice.tts.set_volume(0.8)

# 设置音色（Windows）
agent.voice.voice.tts.set_voice("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_ZH-CN_HUIHUI_11.0")
```

### 查看可用音色（Windows）

```python
voices = agent.voice.voice.tts.engine.getProperty('voices')
for voice in voices:
    print(f"ID: {voice.id}")
    print(f"Name: {voice.name}")
    print("---")
```

## 故障排除

### 无法识别语音

1. 检查麦克风是否正常工作
2. 确认Vosk模型已正确下载
3. 调整麦克风音量

### 语音合成失败

1. Windows系统会自动使用系统语音
2. 安装 pyttsx3: `pip install pyttsx3`
3. 或使用 edge-tts: `pip install edge-tts`

### 依赖问题

```bash
# 重新安装依赖
pip install --upgrade sounddevice soundfile numpy pyttsx3 vosk
```

## 系统要求

- Python 3.8+
- 麦克风
- 扬声器/耳机
- Windows/Linux/Mac

## 技术架构

- **语音识别**: Vosk (离线) / Whisper (备用)
- **语音合成**: pyttsx3 (离线) / edge-tts (在线)
- **音频处理**: sounddevice + soundfile + numpy
- **唤醒词**: 文本匹配（可扩展为Porcupine）

## License

Same as GenericAgent
