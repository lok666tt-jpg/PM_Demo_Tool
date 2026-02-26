import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re

# ==========================================
# 1. 核心初始化 (安全架构)
# ==========================================
try:
    DS_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    ds_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com")

    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    whisper_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") 
except KeyError as e:
    st.error(f"⚠️ 密钥未配置，请在 Streamlit Secrets 中检查 {e}")
    st.stop()

st.set_page_config(page_title="PM原型生成器 V5.0", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 状态管理 (支持快照回溯)
# ==========================================
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "draft_text_input" not in st.session_state:
    st.session_state.draft_text_input = ""
if "history_snapshots" not in st.session_state:
    st.session_state.history_snapshots = [] # 格式：[{"text": "", "html": "", "audio": None}]
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# 角色定义：高保真 B 端专家
SYSTEM_PROMPT = """你是一位世界顶尖的 B 端前端交互专家。使用 Vue3 + Element Plus 构建高保真原型。
【技术要求】：
- 必须是单文件 HTML，严禁使用 <script setup>。
- 必须包含：Vue3, Element Plus, Echarts (用于报表)。
- 页面必须包含真实的 B 端布局 (Header, Sidebar, Main)。
- 模拟跳转：通过 v-if="page === 'xxx'" 切换。
- 拒绝废话，只输出纯净 HTML 代码，不要用 ```html 标记。"""

# ==========================================
# 3. 功能函数
# ==========================================
def transcribe_audio(audio_file):
    try:
        audio_bytes = audio_file.getvalue()
        transcript = whisper_client.audio.transcriptions.create(
            model="whisper-large-v3", 
            file=("audio.wav", audio_bytes), 
            response_format="text"
        )
        return str(transcript)
    except Exception as e:
        return f"【语音解析失败】: {str(e)}"

# 历史回溯函数
def load_snapshot(idx):
    snap = st.session_state.history_snapshots[idx]
    st.session_state.draft_text_input = snap["text"]
    st.session_state.html_code = snap["html"]

# 删除记录
def delete_snapshot(idx):
    st.session_state.history_snapshots.pop(idx)

# ==========================================
# 4. 侧边栏：任务控制台 (历史记录全回显)
# ==========================================
with st.sidebar:
    st.header("⚙️ 任务控制台")
    if st.button("🗑️ 彻底清空当前", use_container_width=True):
        st.session_state.draft_text_input = ""
        st.session_state.html_code = ""
        st.session_state.uploader_key += 1
        st.rerun()

    st.markdown("---")
    st.subheader("🕙 历史版本回溯")
    if not st.session_state.history_snapshots:
        st.caption("暂无历史快照")
    else:
        for i, snap in enumerate(reversed(st.session_state.history_snapshots)):
            real_idx = len(st.session_state.history_snapshots) - 1 - i
            col_sel, col_del = st.columns([4, 1])
            with col_sel:
                # 点击此按钮，右侧所有内容瞬间回显
                if st.button(f"📄 {snap['text'][:15]}...", key=f"snap_{real_idx}", use_container_width=True):
                    load_snapshot(real_idx)
                    st.rerun()
            with col_del:
                st.button("❌", key=f"del_{real_idx}", on_click=delete_snapshot, args=(real_idx,))

st.title("🚀 需求秒转 Demo 工具 (V5.0 旗舰版)")

# ==========================================
# 5. 主布局
# ==========================================
col_in, col_demo = st.columns([1, 1.2])

with col_in:
    st.subheader("🎤 1. 需求多模态录入")
    
    # 支持三种方式并行的选项卡
    input_tab1, input_tab2 = st.tabs(["🎙️ 语音/音频输入", "⌨️ 纯文本输入"])
    
    with input_tab1:
        audio_record = st.audio_input("录音需求", key=f"rec_{st.session_state.uploader_key}")
        audio_upload = st.file_uploader("或上传音频文件", type=['mp3', 'wav', 'm4a'], key=f"file_{st.session_state.uploader_key}")
        
        target_audio = audio_record or audio_upload
        if target_audio:
            if st.button("🎙️ 提取语音内容", type="secondary"):
                with st.spinner("Whisper 正在听取..."):
                    text = transcribe_audio(target_audio)
                    st.session_state.draft_text_input = text
                    st.rerun()

    with input_tab2:
        st.caption("直接在下方编辑区输入或粘贴您的原型需求即可。")
        st.info("💡 比如：设计一个机场航显系统 V3.0 的监控大屏，左侧是航班列表，右侧是延误统计饼图。")

    st.markdown("---")
    st.subheader("✍️ 2. 需求核对与生成")
    
    # 关键：此处内容在生成后不会被清空
    edited_text = st.text_area(
        "最终生成将基于此处文本：",
        value=st.session_state.draft_text_input,
        height=200,
        key="draft_text_input" # 绑定状态
    )

    if st.button("✨ 生成/更新高保真 Demo", type="primary", use_container_width=True):
        if not st.session_state.draft_text_input.strip():
            st.warning("内容为空，无法生成")
        else:
            with st.spinner("DeepSeek 正在构建像素级原型..."):
                try:
                    res = ds_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": st.session_state.draft_text_input}
                        ],
                        temperature=0.3
                    )
                    raw_html = res.choices[0].message.content
                    # 净化代码
                    clean_match = re.search(r'(<!DOCTYPE html>.*</html>|<html.*</html>)', raw_html, re.DOTALL | re.IGNORECASE)
                    final_html = clean_match.group(1).strip() if clean_match else raw_html
                    
                    st.session_state.html_code = final_html
                    
                    # 【核心更新】：保存到快照库
                    st.session_state.history_snapshots.append({
                        "text": st.session_state.draft_text_input,
                        "html": final_html
                    })
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"生成失败: {e}")

with col_demo:
    st.subheader("🖥️ 3. 交互 Demo 预览")
    if st.session_state.html_code:
        st.success("🎉 生成成功！请在下方预览。")
        components.html(st.session_state.html_code, height=800, scrolling=True)
        st.markdown("---")
        st.download_button("⬇️ 下载此版本 HTML", st.session_state.html_code, f"prototype_{len(st.session_state.history_snapshots)}.html", "text/html")
    else:
        st.info("👈 在左侧输入需求并点击生成，Demo 将在此展示。")









