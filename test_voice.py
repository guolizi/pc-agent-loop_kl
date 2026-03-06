"""
Voice Control Test Script
语音控制功能测试脚本
"""

import sys
import os

print("="*60)
print("Voice Control Test for GenericAgent")
print("="*60)
print()

# 测试1: 检查Python版本
print("Test 1: Python Version")
print(f"  Python: {sys.version}")
if sys.version_info < (3, 8):
    print("  ✗ Python 3.8+ required")
    sys.exit(1)
print("  ✓ Python version OK")
print()

# 测试2: 检查依赖
print("Test 2: Dependencies")
dependencies = {
    "numpy": False,
    "sounddevice": False,
    "soundfile": False,
    "pyttsx3": False,
}

for pkg in dependencies:
    try:
        __import__(pkg)
        dependencies[pkg] = True
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  ✗ {pkg} (not installed)")

print()

# 测试3: 检查可选依赖
print("Test 3: Optional Dependencies")
optional = ["vosk", "edge_tts", "whisper", "webrtcvad"]
for pkg in optional:
    try:
        if pkg == "edge_tts":
            __import__("edge_tts")
        elif pkg == "whisper":
            __import__("whisper")
        else:
            __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  - {pkg} (optional, not installed)")

print()

# 测试4: 导入语音模块
print("Test 4: Voice Module Import")
try:
    from voice_simple import SimpleVoiceController, VoiceConfig
    print("  ✓ voice_simple module imported successfully")
    VOICE_MODULE_OK = True
except Exception as e:
    print(f"  ✗ Failed to import voice_simple: {e}")
    VOICE_MODULE_OK = False

print()

# 测试5: 检查Vosk模型
print("Test 5: Vosk Model")
model_paths = [
    "vosk-model-small-cn-0.22",
    "models/vosk-model-small-cn-0.22",
]
model_found = False
for path in model_paths:
    if os.path.exists(path):
        print(f"  ✓ Found: {path}")
        model_found = True
        break

if not model_found:
    print("  ✗ Vosk model not found")
    print("  Please run: python setup_voice.py")
    print("  Or download manually from:")
    print("  https://alphacephei.com/vosk/models")

print()

# 测试6: 初始化语音控制器
print("Test 6: Voice Controller Initialization")
if VOICE_MODULE_OK:
    try:
        config = VoiceConfig(wake_word="你好助手")
        controller = SimpleVoiceController(config)
        
        if controller.is_ready():
            print("  ✓ Voice controller initialized and ready")
            print(f"  ✓ Wake word: {config.wake_word}")
            print(f"  ✓ Sample rate: {config.sample_rate}")
            print(f"  ✓ Interrupt words: {config.interrupt_words}")
        else:
            print("  ✗ Voice controller not ready")
            print("  Some components may be missing")
    except Exception as e:
        print(f"  ✗ Initialization error: {e}")
else:
    print("  - Skipped (module import failed)")

print()

# 测试7: 检查音频设备
print("Test 7: Audio Devices")
try:
    import sounddevice as sd
    devices = sd.query_devices()
    
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    output_devices = [d for d in devices if d['max_output_channels'] > 0]
    
    print(f"  ✓ Input devices: {len(input_devices)}")
    for i, dev in enumerate(input_devices[:3]):  # 显示前3个
        print(f"    [{i}] {dev['name']}")
    
    print(f"  ✓ Output devices: {len(output_devices)}")
    for i, dev in enumerate(output_devices[:3]):
        print(f"    [{i}] {dev['name']}")
    
    if not input_devices:
        print("  ✗ No input devices found (microphone required)")
    if not output_devices:
        print("  ✗ No output devices found (speaker required)")
        
except Exception as e:
    print(f"  ✗ Error checking audio devices: {e}")

print()

# 总结
print("="*60)
print("Test Summary")
print("="*60)

all_deps = all(dependencies.values())
if all_deps and VOICE_MODULE_OK and model_found:
    print("✓ All tests passed! Voice control is ready.")
    print()
    print("To start voice control, run:")
    print("  python voice_agent_integration.py")
    print()
    print("Or with custom wake word:")
    print('  python voice_agent_integration.py --wake-word "小助手"')
else:
    print("✗ Some tests failed. Please fix the issues above.")
    print()
    print("To install dependencies:")
    print("  python setup_voice.py")
    print()
    print("Or manually:")
    print("  pip install sounddevice soundfile numpy pyttsx3 vosk")

print()

# 交互式测试（可选）
if all_deps and VOICE_MODULE_OK:
    print("Would you like to run an interactive test? (y/n)")
    try:
        response = input("> ").strip().lower()
        if response in ['y', 'yes']:
            print()
            print("Interactive Test:")
            print("1. Testing text-to-speech...")
            
            try:
                controller.speak("语音控制测试成功", block=True)
                print("  ✓ TTS test passed")
            except Exception as e:
                print(f"  ✗ TTS test failed: {e}")
            
            print()
            print("2. Testing voice recognition...")
            print("   Please say something after the beep...")
            
            try:
                import time
                time.sleep(1)
                controller.recorder.start_recording()
                time.sleep(3)
                audio = controller.recorder.stop_recording()
                
                if audio is not None:
                    text = controller.recognizer.recognize(audio)
                    if text:
                        print(f"  ✓ Recognized: '{text}'")
                        controller.speak(f"识别到：{text}", block=False)
                    else:
                        print("  - No speech recognized (this is OK)")
                else:
                    print("  ✗ No audio recorded")
            except Exception as e:
                print(f"  ✗ Recognition test failed: {e}")
    except (KeyboardInterrupt, EOFError):
        print("\nTest cancelled.")

print()
print("Test complete!")
