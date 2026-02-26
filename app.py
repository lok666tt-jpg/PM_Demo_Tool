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

st.set_page_config(page_title="PM原型生成器 V4.5", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 全局状态管理 & 侧边栏 
# ==========================================
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft_text_input" not in st.session_state: 
    st.session_state.draft_text_input = ""
# 【核心新增】：用于强行重置录音/上传组件的动态标识
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

system_prompt = """你是一个资深的 B端产品经理兼前端架构师。
你的任务是根据用户的需求，生成 Vue3 + Element Plus 的单文件 HTML 代码。
【要求】：
- 必须引入 Vue3 和 Element Plus 的 CDN。
- 使用 Mock 数据写死在前端。
- 只输出最终的 HTML 代码，不要输出任何解释说明。
- 绝对不要输出 ```html 开头的标记，直接输出 <html 标签开头的纯代码！"""

if len(st.session_state.messages) == 0:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# 【核心新增】：精细化删除单条历史记录的回调函数
def delete_history_item(idx):
    # 确保删掉的是用户需求
    if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "user":
        st.session_state.messages.pop(idx)
        # 如果紧接着的一条是 AI 的旧回复，一并剔除，保持上下文干净
        if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "assistant":
            st.session_state.messages.pop(idx)

# 侧边栏：历史记录与独立管理
with st.sidebar:
    st.header("⚙️ 任务控制台")
    
    # 【修复】：现在的按钮只清空当前没生成的草稿和麦克风，不碰历史
    if st.button("🧹 清空当前录音与输入", use_container_width=True):
        st.session_state.draft_text_input = ""
        st.session_state.uploader_key += 1 # 变更 Key，强制卸载并刷新多媒体组件
        st.rerun()
        
    st.markdown("---")
    st.subheader("📝 历史需求管理")
    
    has_history = False
    # 【修复】：为每条历史记录生成独立的删除按钮
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            has_history = True
            col_text, col_btn = st.columns([5, 1]) # 左右比例分配
            with col_text:
                st.info(msg["content"][:30] + "..." if len(msg["content"]) > 30 else msg["content"])
            with col_btn:
                # 绑定回调函数进行精准删除
                st.button("❌", key=f"del_{i}", on_click=delete_history_item, args=(i,), help="删除此条需求")
                
    if not has_history:
        st.caption("暂无记录")

st.title("🚀 需求秒转 Demo 工具 (V4.5 颗粒管理版)")

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
        # 稳妥的解析格式兼容
        if hasattr(transcript, 'text'):
            return transcript.text
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
    
    # 绑定动态 Key，点击侧边栏的“清空当前”时，它们会自动变回没录音的初始状态
    audio_file = st.audio_input("直接点击麦克风说出你的需求", key=f"audio_{st.session_state.uploader_key}")
    uploaded_file = st.file_uploader("或上传录音文件 (mp3/wav)", type=['mp3', 'wav', 'm4a'], key=f"file_{st.session_state.uploader_key}")
    
    target_audio = audio_file or uploaded_file
    
    if target_audio:
        if st.button("🔄 第1步：提取语音为文本"):
            with st.spinner("极速引擎正在提取语音..."):
                transcribed_text = transcribe_audio_to_text(target_audio)
                if "【语音解析失败】" in transcribed_text:
                    st.error(transcribed_text)
                else:
                    st.success("✅ 提取成功！请在下方核对修改。")
                    st.session_state.draft_text_input = transcribed_text
                    st.rerun()

    st.markdown("---")
    st.subheader("✍️ 2. 需求核对与编辑")
    
    edited_text = st.text_area(
        "确认无误后，点击下方按钮生成页面：", 
        height=150,
        key="draft_text_input" 
    )

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
                    
                    match = re.search(r'```(?:html|vue)?(.*?)```', ai_result, re.DOTALL | re.IGNORECASE)
                    if match:
                        new_html = match.group(1).strip()
                    else:
                        new_html = ai_result.replace("```html", "").replace("```", "").strip()
                    
                    st.session_state.html_code = new_html
                    st.session_state.messages.append({"role": "assistant", "content": "已生成代码"})
                    
                    # 生成成功后，清空草稿并重置麦克风，准备迎接下一次录音
                    st.session_state.draft_text_input = ""
                    st.session_state.uploader_key += 1 
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





