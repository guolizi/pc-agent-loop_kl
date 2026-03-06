"""
Streamlit Voice Interface for GenericAgent
带语音控制的Streamlit界面
"""

import os
import sys
if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")
try: sys.stdout.reconfigure(errors='replace')
except: pass
try: sys.stderr.reconfigure(errors='replace')
except: pass
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import time
import json
import re
import threading
from agentmain import GeneraticAgent

# 尝试导入语音模块
try:
    from voice_simple import SimpleVoiceController, VoiceConfig
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

st.set_page_config(page_title="Cowork - Voice", layout="wide")

# 初始化Agent
@st.cache_resource
def init_agent():
    agent = GeneraticAgent()
    if agent.llmclient is None:
        return None
    threading.Thread(target=agent.run, daemon=True).start()
    return agent

# 初始化语音控制器
def init_voice_controller():
    if not VOICE_AVAILABLE:
        return None
    
    try:
        config = VoiceConfig(
            wake_word=st.session_state.get('wake_word', '你好助手'),
            enable_interrupt=True
        )
        controller = SimpleVoiceController(config)
        
        # 设置回调
        controller.on_speech = lambda text: handle_voice_input(text)
        controller.on_interrupt = lambda: handle_interrupt()
        
        return controller
    except Exception as e:
        st.error(f"Voice initialization error: {e}")
        return None

def handle_voice_input(text: str):
    """处理语音输入"""
    st.session_state.voice_input_queue.put(text)

def handle_interrupt():
    """处理打断"""
    if 'agent' in st.session_state and st.session_state.agent:
        st.session_state.agent.abort()

# 初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'voice_enabled' not in st.session_state:
    st.session_state.voice_enabled = False
if 'tts_enabled' not in st.session_state:
    st.session_state.tts_enabled = True
if 'wake_word' not in st.session_state:
    st.session_state.wake_word = "你好助手"
if 'voice_controller' not in st.session_state:
    st.session_state.voice_controller = None
if 'voice_input_queue' not in st.session_state:
    st.session_state.voice_input_queue = None
if 'last_reply_time' not in st.session_state:
    st.session_state.last_reply_time = 0

# 初始化Agent
agent = init_agent()
if agent is None:
    st.error("⚠️ 未配置任何可用的 LLM 接口，请在 mykey.py 中添加配置后重启。")
    st.stop()

st.session_state.agent = agent

# 初始化语音队列
if st.session_state.voice_input_queue is None:
    st.session_state.voice_input_queue = []

st.title("🎙️ Cowork with Voice")

# 侧边栏
with st.sidebar:
    st.header("🎤 Voice Control")
    
    # 语音输入开关
    voice_enabled = st.toggle(
        "启用语音输入",
        value=st.session_state.voice_enabled,
        help="开启后可以通过语音与Agent交互"
    )
    
    if voice_enabled != st.session_state.voice_enabled:
        st.session_state.voice_enabled = voice_enabled
        if voice_enabled:
            if VOICE_AVAILABLE:
                st.session_state.voice_controller = init_voice_controller()
                if st.session_state.voice_controller and st.session_state.voice_controller.is_ready():
                    st.session_state.voice_controller.start()
                    st.success(f"语音控制已启动，唤醒词：'{st.session_state.wake_word}'")
                else:
                    st.error("语音控制初始化失败，请检查依赖")
                    st.session_state.voice_enabled = False
            else:
                st.error("语音模块未安装，请运行: pip install sounddevice soundfile numpy pyttsx3 vosk")
                st.session_state.voice_enabled = False
        else:
            if st.session_state.voice_controller:
                st.session_state.voice_controller.stop()
            st.info("语音控制已停止")
        st.rerun()
    
    # TTS开关
    tts_enabled = st.toggle(
        "启用语音合成",
        value=st.session_state.tts_enabled,
        help="开启后Agent会通过语音回复"
    )
    st.session_state.tts_enabled = tts_enabled
    
    # 唤醒词设置
    if st.session_state.voice_enabled:
        new_wake_word = st.text_input(
            "唤醒词",
            value=st.session_state.wake_word,
            help="说出这个词唤醒Agent"
        )
        if new_wake_word != st.session_state.wake_word:
            st.session_state.wake_word = new_wake_word
            if st.session_state.voice_controller:
                st.session_state.voice_controller.config.wake_word = new_wake_word
            st.success(f"唤醒词已更新为: '{new_wake_word}'")
    
    st.divider()
    
    # LLM设置
    st.header("🤖 LLM Settings")
    current_idx = agent.llm_no
    st.caption(f"Current: {agent.get_llm_name()}")
    
    if st.button("切换备用链路"):
        agent.next_llm()
        st.rerun()
    
    if st.button("强行停止任务"):
        agent.abort()
        if st.session_state.voice_controller:
            st.session_state.voice_controller.tts.stop()
        st.toast("已发送停止信号")
        st.rerun()
    
    st.divider()
    
    # 状态显示
    st.header("📊 Status")
    if st.session_state.voice_enabled and st.session_state.voice_controller:
        status = st.session_state.voice_controller.is_ready()
        st.write(f"语音控制: {'🟢 运行中' if status else '🔴 未就绪'}")
    else:
        st.write("语音控制: ⚪ 已禁用")
    
    st.write(f"语音合成: {'🟢 开启' if st.session_state.tts_enabled else '⚪ 关闭'}")
    
    if st.session_state.last_reply_time > 0:
        idle_time = int(time.time()) - st.session_state.last_reply_time
        st.write(f"空闲时间: {idle_time}秒")

# 主界面
st.markdown("""
### 🎯 使用说明

**语音交互：**
1. 在侧边栏启用"语音输入"
2. 说出唤醒词（默认："你好助手"）
3. 听到提示音后说出你的指令
4. Agent会自动处理并语音回复
5. 说"停"或"停止"可以打断

**文字交互：**
- 直接在下方输入框输入文字
- 支持所有原有的Agent功能
""")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理语音输入
if st.session_state.voice_enabled and st.session_state.voice_controller:
    # 检查语音输入队列
    if hasattr(st.session_state.voice_controller, '_speech_buffer'):
        # 这里需要一种方式来获取语音输入
        # 由于Streamlit的限制，我们使用一个变通方法
        pass

# 文本输入
if prompt := st.chat_input("请输入指令或说话..."):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 提交任务
    display_queue = agent.put_task(prompt, source="user")
    
    # 显示Agent回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            while True:
                item = display_queue.get(timeout=120)
                
                if 'next' in item:
                    full_response = item['next']
                    message_placeholder.markdown(full_response + "▌")
                
                if 'done' in item:
                    full_response = item['done']
                    message_placeholder.markdown(full_response)
                    
                    # TTS
                    if st.session_state.tts_enabled and st.session_state.voice_controller:
                        # 清理文本
                        clean_text = re.sub(r'```[\s\S]*?```', ' [代码] ', full_response)
                        clean_text = re.sub(r'`[^`]*`', ' [代码] ', clean_text)
                        clean_text = re.sub(r'https?://\S+', ' [链接] ', clean_text)
                        clean_text = re.sub(r'[#*_\[\](){}]', ' ', clean_text)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        
                        # 限制长度
                        if len(clean_text) > 500:
                            clean_text = clean_text[:500] + " ... [内容过长]"
                        
                        if clean_text:
                            st.session_state.voice_controller.speak(clean_text, block=False)
                    
                    break
        
        except queue.Empty:
            message_placeholder.markdown(full_response + "\n\n[Timeout]")
        except Exception as e:
            message_placeholder.markdown(full_response + f"\n\n[Error: {e}]")
    
    # 保存消息
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.session_state.last_reply_time = int(time.time())
    
    # 限制历史记录长度
    if len(st.session_state.messages) > 20:
        st.session_state.messages = st.session_state.messages[-20:]

# 语音状态指示器
if st.session_state.voice_enabled:
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.session_state.voice_controller and st.session_state.voice_controller.is_awake:
            st.success("🎤 正在监听...")
        else:
            st.info(f"⏳ 等待唤醒词: '{st.session_state.wake_word}'")
    
    with col2:
        if st.session_state.voice_controller and st.session_state.voice_controller.tts.speaking:
            st.warning("🔊 正在播放...")
        else:
            st.empty()
    
    with col3:
        if st.button("🛑 打断"):
            agent.abort()
            if st.session_state.voice_controller:
                st.session_state.voice_controller.tts.stop()
            st.rerun()

# 页脚
st.markdown("---")
st.caption("💡 Tip: 语音控制需要麦克风权限。如果无法使用，请检查浏览器设置和系统权限。")
