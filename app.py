import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re

# ==========================================
# 1. 初始化两套大模型客户端 (完全解耦架构)
# --- 🧠 大脑：DeepSeek (负责写代码) ---
DS_API_KEY = "sk-8269c6bca93e4c57a4d4f0e3494550dc" # 👉 填入 DeepSeek Key
ds_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com")

# --- 👂 耳朵：Groq (提供免费且极速的 Whisper 语音识别) ---
GROQ_API_KEY = "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" # 👉 填入刚才申请的以 gsk_ 开头的 Key
# Groq 的接口完全兼容 OpenAI SDK，只需换个 Base URL 即可
whisper_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") 

st.set_page_config(page_title="PM原型生成器 V4.2", layout="wide", initial_sidebar_state="collapsed")
st.title("🚀 需求秒转 Demo 工具 (V4.2 极速语音版)")

# ==========================================
# 🔌 核心模块：音频转文字
# ==========================================
def transcribe_audio_to_text(audio_file):
    try:
        # Streamlit 传入的可能是纯内存对象，为了兼容接口，加上标准后缀
        audio_file.name = "audio.wav" 
        
        # 调用 Groq 提供的免费 whisper-large-v3 模型
        transcript = whisper_client.audio.transcriptions.create(
            model="whisper-large-v3", 
            file=audio_file,
            response_format="text" # 直接要求返回纯文本
        )
        return transcript
    except Exception as e:
        return f"【语音解析失败】：请检查 Groq Key 是否正确。详细报错：{str(e)}"

# 3. 初始化会话记忆
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# 强制注入 System Prompt
system_prompt = """你是一个资深的 B端产品经理兼前端架构师。
你的任务是根据用户的需求或会议录音转录文本，生成 Vue3 + Element Plus 的单文件 HTML 代码。
【要求】：
- 必须引入 Vue3 和 Element Plus 的 CDN。
- 使用 Mock 数据写死在前端。
- 只输出最终的 HTML 代码，用 ```html 和 ``` 包裹。"""

if len(st.session_state.messages) == 0:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# 4. 界面布局：左右分栏
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🎤 1. 需求输入")
    
    input_mode = st.radio("选择输入方式：", ["⌨️ 文本输入", "🎙️ 录音/上传音频"], horizontal=True)
    
    if input_mode == "⌨️ 文本输入":
        user_input = st.chat_input("输入需求，例如：生成航显系统的数据面板...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
    else:
        st.info("💡 提示：本版本已接入 Groq 极速语音解析引擎。")
        audio_file = st.audio_input("直接点击麦克风说出你的需求")
        uploaded_file = st.file_uploader("或上传录音文件 (mp3/wav)", type=['mp3', 'wav', 'm4a'])
        
        target_audio = audio_file or uploaded_file
        
        if target_audio:
            if st.button("🔄 开始转录并生成界面", type="primary"):
                with st.spinner("极速引擎正在提取语音需求..."):
                    # 调用语音识别
                    transcribed_text = transcribe_audio_to_text(target_audio)
                    
                    if "【语音解析失败】" in transcribed_text:
                        st.error(transcribed_text)
                    else:
                        st.success("✅ 转录成功！")
                        st.info(f"📄 转录内容：\n{transcribed_text}")
                        
                        # 自动喂给大模型
                        st.session_state.messages.append({"role": "user", "content": f"以下是会议录音内容，请据此生成或修改页面：\n{transcribed_text}"})
                        st.rerun()

    # 当有新需求加入时，触发 DeepSeek 生成代码
    if len(st.session_state.messages) > 1 and st.session_state.messages[-1]["role"] == "user":
        with st.spinner("AI 正在构建前端组件中..."):
            try:
                response = ds_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=st.session_state.messages,
                    temperature=0.2 
                )
                ai_result = response.choices[0].message.content
                match = re.search(r'```html(.*?)```', ai_result, re.DOTALL)
                new_html = match.group(1).strip() if match else ai_result.strip()
                
                st.session_state.html_code = new_html
                st.session_state.messages.append({"role": "assistant", "content": ai_result})
                st.rerun()
            except Exception as e:
                st.error(f"代码生成出错: {e}")

with col2:
    st.subheader("🖥️ 2. 交互 Demo")
    if st.session_state.html_code:
        components.html(st.session_state.html_code, height=750, scrolling=True)
        st.download_button("⬇️ 下载 HTML", st.session_state.html_code, "demo_prototype.html", "text/html")
    else:
        st.info("👈 请在左侧输入需求或直接录音。")
