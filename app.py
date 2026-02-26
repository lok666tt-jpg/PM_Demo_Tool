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

st.set_page_config(page_title="PM原型生成器 V4.7", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 2. 全局状态管理 & 侧边栏 
# ==========================================
if "html_code" not in st.session_state:
    st.session_state.html_code = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft_text_input" not in st.session_state: 
    st.session_state.draft_text_input = ""
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# 【优化2】：史诗级增强的 System Prompt，追求高保真 B 端风格
system_prompt = """你是一位世界顶尖的 B 端前端交互专家，专注于使用 Vue3 + Element Plus 构建高保真、专业级的管理后台界面原型。

你的目标不仅仅是实现功能，更是要创造出布局合理、视觉美观、数据真实的页面，可以直接用于向客户进行专业演示。

【严格要求】：
1.  **技术栈**：必须使用 Vue 3 (推荐 `<script setup>`) 和 Element Plus CDN。
2.  **专业布局**：
    * 拒绝简单的组件堆砌。必须使用标准的 B 端布局结构，例如用 `<el-card shadow="never">` 来包裹主要内容区域，提供干净的白色背景和细腻的边框。
    * 页面要有合理的内边距 (Padding)，通常主内容区需要 20px 的 padding，不要让组件紧贴浏览器边缘。
    * 使用 `<el-row>` 和 `<el-col>` 进行合理的栅格布局。
3.  **高保真组件与数据**：
    * **表格**：如果需要列表，必须使用 `<el-table>`，并包含真实的列（如状态标签 `<el-tag>`、操作按钮组、真实的日期时间），底部必须配一个静态的 `<el-pagination>` 分页器。
    * **表单**：表单项要有清晰的 Label，合理的输入框宽度，必要时使用行内表单布局。
    * **数据**：填充极其真实的 Mock 数据（例如：真实的人名、看起来像样的订单号、'已完成/处理中'的状态、'2023-10-27 14:30' 格式的时间），绝不允许出现 "test", "abc" 这种敷衍数据。
4.  **微交互**：为关键按钮（如“保存”、“提交”、“搜索”）添加简单的 `@click` 事件，弹出 `ElMessage.success('操作成功，演示模式数据未保存')` 之类的提示，让 Demo 活起来。
5.  **输出格式**：只输出最终的 HTML 文件内容（以 `<!DOCTYPE html>` 开头），不要包含任何 markdown 标记（如 ```html）。"""

if len(st.session_state.messages) == 0:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

def delete_history_item(idx):
    if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "user":
        st.session_state.messages.pop(idx)
        if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "assistant":
            st.session_state.messages.pop(idx)

with st.sidebar:
    st.header("⚙️ 任务控制台")
    
    # 【优化1】：此按钮是唯一能清空文本框的地方
    if st.button("🧹 清空当前录音与输入", use_container_width=True):
        st.session_state.draft_text_input = "" # 手动清空文本
        st.session_state.uploader_key += 1 # 重置录音控件
        st.rerun()
        
    st.markdown("---")
    st.subheader("📝 历史需求管理")
    
    has_history = False
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            has_history = True
            col_text, col_btn = st.columns([5, 1]) 
            with col_text:
                st.info(msg["content"][:30] + "..." if len(msg["content"]) > 30 else msg["content"])
            with col_btn:
                st.button("❌", key=f"del_{i}", on_click=delete_history_item, args=(i,), help="删除此条需求")
                
    if not has_history:
        st.caption("暂无记录")

st.title("🚀 需求秒转 Demo 工具 (V4.7 高保真专业版)")

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
            
            with st.spinner("AI 正在构建专业级前端组件中 (约需15-25秒)..."):
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
                    
                    # 【优化1】：生成成功后，不再自动清空文本框！
                    # 只重置录音控件，方便下一次录音
                    st.session_state.uploader_key += 1 
                    st.rerun()
                except Exception as e:
                    st.error(f"代码生成出错: {e}")

with col2:
    st.subheader("🖥️ 3.






