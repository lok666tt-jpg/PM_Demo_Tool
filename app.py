import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re

# ==========================================
# 1. 初始化两套大模型客户端 (安全架构)
# ==========================================
try:
    DS_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    ds_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com")

    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    whisper_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") 
except KeyError as e:
    st.error(f"⚠️ 缺少 API Key 配置: 找不到 {e}。请在 Streamlit Cloud 中配置。")
    st.stop()

st.set_page_config(page_title="PM原型生成器 V4.4", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 全局状态管理 & 侧边栏 
# ==========================================
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# 【修复点1】：直接初始化绑定的 key，丢弃多余的变量
if "draft_text_input" not in st.session_state: 
    st.session_state.draft_text_input = ""

system_prompt = """你是一个资深的 B端产品经理兼前端架构师。
你的任务是根据用户的需求，生成 Vue3 + Element Plus 的单文件 HTML 代码。
【要求】：
- 必须引入 Vue3 和 Element Plus 的 CDN。
- 使用 Mock 数据写死在前端。
- 只输出最终的 HTML 代码，不要输出任何解释说明。
- 绝对不要输出 ```html 开头的标记，直接输出 <html 标签开头的纯代码！"""

if len(st.session_state.messages) == 0:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# 侧边栏：历史记录与一键重置
with st.sidebar:
    st.header("⚙️ 任务控制台")
    if st.button("🗑️ 清空重置 (开启新需求)", type="primary", use_container_width=True):
        st.session_state.html_code = ""
        st.session_state.draft_text_input = "" # 【修复点2】：重置时直接清空 key
        st.session_state.messages = [{"role": "system", "content": system_prompt}]
        st.rerun()
        
    st.markdown("---")
    st.subheader("📝 历史需求暂存")
    has_history = False
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.info(msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"])
            has_history = True
    if not has_history:
        st.caption("暂无记录")

st.title("🚀 需求秒转 Demo 工具 (V4.4 稳定版)")

# ==========================================
# 3. 核心接口：音频转文字
# ==========================================
def transcribe_audio_to_text(audio_file):
    try:
        audio_bytes = audio_file.getvalue()
        transcript = whisper_client.audio.transcriptions.create(
            model="whisper-large-v3", 
            file=("audio.wav", audio_bytes), 
            response_format="text"
        )
        # 强制转换为字符串格式，确保 Streamlit 能正确渲染
        return str(transcript)
    except Exception as e:
        return f"【语音解析失败】: {str(e)}"

# ==========================================
# 4. 界面布局：左右分栏
# ==========================================
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🎤 1. 录音提取")
    st.info("💡 提示：录音提取后不会直接消耗 Token，请在下方文本框修改确认后再生成。")
    
    audio_file = st.audio_input("直接点击麦克风说出你的需求")
    uploaded_file = st.file_uploader("或上传录音文件 (mp3/wav)", type=['mp3', 'wav', 'm4a'])
    
    target_audio = audio_file or uploaded_file
    
    if target_audio:
        if st.button("🔄 第1步：提取语音为文本"):
            with st.spinner("极速引擎正在提取语音..."):
                transcribed_text = transcribe_audio_to_text(target_audio)
                if "【语音解析失败】" in transcribed_text:
                    st.error(transcribed_text)
                else:
                    st.success("✅ 提取成功！请在下方核对修改。")
                    # 【修复点3】：将提取的内容直接赋值给组件绑定的 key！




