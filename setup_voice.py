"""
Voice Control Setup Script
语音控制功能安装脚本
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令"""
    if description:
        print(f"\n{description}")
    print(f"> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    if result.stdout:
        print(result.stdout)
    return True


def install_packages():
    """安装必要的Python包"""
    print("="*60)
    print("Installing required packages...")
    print("="*60)
    
    packages = [
        "sounddevice",      # 音频输入输出
        "soundfile",        # 音频文件处理
        "numpy",            # 数值计算
        "pyttsx3",          # 离线TTS
        "vosk",             # 离线语音识别
    ]
    
    # 可选包
    optional_packages = [
        "edge-tts",         # 在线TTS（高质量）
        "openai-whisper",   # 备用语音识别
        "webrtcvad",        # 语音活动检测
    ]
    
    # 安装必需包
    for pkg in packages:
        run_command(f"{sys.executable} -m pip install {pkg}", f"Installing {pkg}...")
    
    # 尝试安装可选包
    print("\nInstalling optional packages...")
    for pkg in optional_packages:
        run_command(f"{sys.executable} -m pip install {pkg}", f"Installing {pkg} (optional)...")
    
    print("\n✓ Package installation complete!")


def download_vosk_model():
    """下载Vosk中文模型"""
    print("\n" + "="*60)
    print("Downloading Vosk Chinese Model...")
    print("="*60)
    
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
    model_file = "vosk-model-small-cn-0.22.zip"
    model_dir = "vosk-model-small-cn-0.22"
    
    # 检查是否已存在
    if os.path.exists(model_dir):
        print(f"Model already exists: {model_dir}")
        return True
    
    # 下载
    print(f"Downloading from {model_url}...")
    print("This may take a few minutes...")
    
    try:
        urllib.request.urlretrieve(model_url, model_file)
        print(f"✓ Downloaded: {model_file}")
        
        # 解压
        print("Extracting...")
        with zipfile.ZipFile(model_file, 'r') as zip_ref:
            zip_ref.extractall(".")
        print(f"✓ Extracted to: {model_dir}")
        
        # 删除zip文件
        os.remove(model_file)
        print(f"✓ Removed: {model_file}")
        
        return True
    
    except Exception as e:
        print(f"Error downloading model: {e}")
        print("\nPlease manually download from:")
        print(model_url)
        print(f"And extract to: {os.path.abspath('.')}")
        return False


def test_installation():
    """测试安装"""
    print("\n" + "="*60)
    print("Testing Installation...")
    print("="*60)
    
    tests = []
    
    # 测试numpy
    try:
        import numpy as np
        tests.append(("numpy", True, f"version {np.__version__}"))
    except ImportError:
        tests.append(("numpy", False, "not installed"))
    
    # 测试sounddevice
    try:
        import sounddevice as sd
        tests.append(("sounddevice", True, f"version {sd.__version__}"))
    except ImportError:
        tests.append(("sounddevice", False, "not installed"))
    
    # 测试soundfile
    try:
        import soundfile as sf
        tests.append(("soundfile", True, f"version {sf.__version__}"))
    except ImportError:
        tests.append(("soundfile", False, "not installed"))
    
    # 测试pyttsx3
    try:
        import pyttsx3
        tests.append(("pyttsx3", True, "installed"))
    except ImportError:
        tests.append(("pyttsx3", False, "not installed"))
    
    # 测试vosk
    try:
        import vosk
        tests.append(("vosk", True, f"version {vosk.__version__}"))
    except ImportError:
        tests.append(("vosk", False, "not installed"))
    
    # 打印结果
    print("\nTest Results:")
    print("-" * 40)
    for name, success, info in tests:
        status = "✓" if success else "✗"
        print(f"{status} {name}: {info}")
    
    # 检查模型
    model_exists = os.path.exists("vosk-model-small-cn-0.22")
    print(f"{'✓' if model_exists else '✗'} Vosk model: {'found' if model_exists else 'not found'}")
    
    # 总体状态
    all_passed = all(success for _, success, _ in tests) and model_exists
    
    if all_passed:
        print("\n✓ All tests passed! Voice control is ready.")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
    
    return all_passed


def create_launcher():
    """创建启动脚本"""
    print("\n" + "="*60)
    print("Creating Launcher Scripts...")
    print("="*60)
    
    # Windows批处理脚本
    bat_content = """@echo off
chcp 65001 >nul
echo Starting Voice-Enabled GenericAgent...
echo.
python voice_agent_integration.py %*
pause
"""
    
    with open("start_voice.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    print("✓ Created: start_voice.bat")
    
    # Python启动脚本
    py_content = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Voice Agent Launcher
语音控制启动器
\"\"\"

import sys
from voice_agent_integration import main

if __name__ == "__main__":
    main()
"""
    
    with open("voice_launcher.py", "w", encoding="utf-8") as f:
        f.write(py_content)
    print("✓ Created: voice_launcher.py")
    
    # README
    readme_content = """# Voice Control for GenericAgent

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
agent.voice.voice.tts.set_voice("HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_ZH-CN_HUIHUI_11.0")
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
"""
    
    with open("VOICE_README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("✓ Created: VOICE_README.md")


def main():
    """主函数"""
    print("="*60)
    print("GenericAgent Voice Control Setup")
    print("="*60)
    print()
    
    # 安装包
    install_packages()
    
    # 下载模型
    download_vosk_model()
    
    # 测试
    test_installation()
    
    # 创建启动器
    create_launcher()
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print("\nTo start voice control, run:")
    print("  Windows: start_voice.bat")
    print("  Python:  python voice_agent_integration.py")
    print("\nFor more information, see VOICE_README.md")


if __name__ == "__main__":
    main()
