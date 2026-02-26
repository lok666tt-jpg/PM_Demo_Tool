import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re

# ==========================================
# 1. 初始化两套大模型客户端 (安全架构)
# ==========================================
try:
    DS_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    ds_client = OpenAI(api_key=DS_API_KEY, base_url="[https://api.deepseek.com](https://api.deepseek.com)")

    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    whisper_client = OpenAI(api_key=GROQ_API_KEY, base_url="[https://api.groq.com/openai/v1](https://api.groq.com/openai/v1)") 
except KeyError as e:
    st.error(f"⚠️ 缺少 API Key 配置: 找不到 {e}。请在 Streamlit Cloud 中配置。")
    st.stop()

st.set_page_config(page_title="PM原型生成器 V4.3", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 全局状态管理 & 侧边栏 (解决你的第二个痛点)
# ==========================================
# 初始化各个状态
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft_text" not in st.session_state: # 新增：用于暂存转录后的文本
    st.session_state.draft_text = ""

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
        # 彻底清空所有数据，恢复初始状态
        st.session_state.html_code = ""
        st.session_state.draft_text = ""
        st.session_state.messages = [{"role": "system", "content": system_prompt}]
        st.rerun()
        
    st.markdown("---")
    st.subheader("📝 历史需求暂存")
    # 展示本次会话中所有提交过的需求记录
    has_history = False
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.info(msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"])
            has_history = True
    if not has_history:
        st.caption("暂无记录")

st.title("🚀 需求秒转 Demo 工具 (V4.3 人机协同版)")

# ==========================================
# 3. 核心接口：音频转文字
# ==========================================
def transcribe_audio_to_text(audio_file):
    try:
        audio_file.name = "audio.wav" 
        transcript = whisper_client.audio.transcriptions.create(
            model="whisper-large-v3", 
            file=audio_file,
            response_format="text"
        )
        return transcript
    except Exception as e:
        return f"【语音解析失败】: {str(e)}"

# ==========================================
# 4. 界面布局：左右分栏
# ==========================================
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("🎤 1. 录音提取")
    st.info("💡 提示：录音提取后不会直接消耗 Token，请在下方文本框修改确认后再生成。")
    
    # 语音输入区
    audio_file = st.audio_input("直接点击麦克风说出你的需求")
    uploaded_file = st.file_uploader("或上传录音文件 (mp3/wav)", type=['mp3', 'wav', 'm4a'])
    
    target_audio = audio_file or uploaded_file
    
    if target_audio:
        # 第一步：仅仅提取文字，不调用大模型生成代码！
        if st.button("🔄 第1步：提取语音为文本"):
            with st.spinner("极速引擎正在提取语音..."):
                transcribed_text = transcribe_audio_to_text(target_audio)
                if "【语音解析失败】" in transcribed_text:
                    st.error(transcribed_text)
                else:
                    st.success("✅ 提取成功！请在下方核对修改。")
                    # 将提取的内容存入编辑框绑定的状态中
                    st.session_state.draft_text = transcribed_text
                    st.rerun()

    st.markdown("---")
    st.subheader("✍️ 2. 需求核对与编辑")
    # 用户可以在这里随意修改提取出来的错别字，或者直接打字输入
    edited_text = st.text_area(
        "确认无误后，点击下方按钮生成页面：", 
        value=st.session_state.draft_text, 
        height=150,
        key="draft_text_input" # 绑定动态输入
    )

    # 第二步：用户确认无误后，才触发 Token 消耗去生成页面
    if st.button("✨ 第2步：生成 / 更新交互 Demo", type="primary"):
        if not st.session_state.draft_text_input.strip():
            st.warning("请先输入或提取需求文本！")
        else:
            final_requirement = st.session_state.draft_text_input
            st.session_state.messages.append({"role": "user", "content": final_requirement})
            
            with st.spinner("AI 正在构建前端组件中 (约需10-20秒)..."):
                try:
                    response = ds_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=st.session_state.messages,
                        temperature=0.2 
                    )
                    ai_result = response.choices[0].message.content
                    
                    # 优化后的防乱码正则表达式提取
                    match = re.search(r'```(?:html|vue)?(.*?)```', ai_result, re.DOTALL | re.IGNORECASE)
                    if match:
                        new_html = match.group(1).strip()
                    else:
                        # 兜底处理：如果模型没写 ``` 包裹，强行去掉可能存在的干扰字符
                        new_html = ai_result.replace("```html", "").replace("```", "").strip()
                    
                    st.session_state.html_code = new_html
                    st.session_state.messages.append({"role": "assistant", "content": "已生成代码"})
                    
                    # 生成完毕后，清空草稿箱，准备下一次输入
                    st.session_state.draft_text = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"代码生成出错: {e}")

with col2:
    st.subheader("🖥️ 3. 交互 Demo")
    if st.session_state.html_code:
        components.html(st.session_state.html_code, height=750, scrolling=True)
        st.download_button("⬇️ 下载 HTML", st.session_state.html_code, "demo_prototype.html", "text/html")
    else:
        st.info("👈 等待接收需求指令...")


