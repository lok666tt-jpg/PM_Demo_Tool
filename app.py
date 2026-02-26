import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re
import time  # 新增：用于处理网络重试的等待时间

# ==========================================
# 1. 初始化大模型客户端 (安全架构)
# ==========================================
try:
    DS_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    ds_client = OpenAI(api_key=DS_API_KEY, base_url="https://api.deepseek.com")

    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    whisper_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") 
except KeyError as e:
    st.error(f"⚠️ 缺少 API Key 配置: 找不到 {e}。请在 Streamlit Cloud 的 Advanced Settings -> Secrets 中配置。")
    st.stop()

st.set_page_config(page_title="PM原型生成器 V5.0", layout="wide", initial_sidebar_state="expanded")

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
if "need_clear_draft" not in st.session_state:
    st.session_state.need_clear_draft = False
if "show_success_effect" not in st.session_state:
    st.session_state.show_success_effect = False

# 延迟清空逻辑：在画界面前安全地清空草稿箱
if st.session_state.need_clear_draft:
    st.session_state.draft_text_input = ""
    st.session_state.need_clear_draft = False

# 【底层架构锁定模板】防白屏、防乱码、支持图表与页面模拟切换
system_prompt = """你是一位世界顶尖的 B 端前端交互专家，专注于使用 Vue3 + Element Plus 构建高保真原型。

【极其重要的技术架构限制（防报错必读）】：
最终代码是在浏览器直接打开的单文件 HTML。绝对禁止使用 <script setup> 语法！
必须严格套用以下模板骨架，填入你的业务代码：

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/element-plus/dist/index.css" />
  <script src="https://unpkg.com/element-plus"></script>
  <script src="https://unpkg.com/@element-plus/icons-vue"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <style>
    /* 在这里写自定义 CSS，例如全屏背景、登录框居中等 */
    body { margin: 0; padding: 0; background-color: #f0f2f5; font-family: sans-serif; }
  </style>
</head>
<body>
  <div id="app">
    <template v-if="currentPage === 'login'">
        </template>
    
    <template v-if="currentPage === 'home'">
        </template>
  </div>
  
  <script>
    const { createApp, ref, reactive, onMounted, nextTick } = Vue;
    const app = createApp({
      setup() {
        const currentPage = ref('login'); // 状态驱动页面跳转
        // 你的响应式数据和逻辑写在这里
        
        return { currentPage, /* 返回所有模板中使用的变量和方法 */ };
      }
    });
    app.use(ElementPlus);
    app.mount("#app");
  </script>
</body>
</html>

【核心要求】：
1. 需求还原度100%：用户要求的输入框、按钮等必须全部画出来！
2. 页面跳转模拟：在一个文件内，用 v-if 结合按钮点击事件改变 currentPage 来模拟跳转。
3. B端高保真：登录页要有好看的居中卡片（带阴影）；后台首页要有侧边栏导航和顶部 Header，内容区用 Echarts 绘制图表。
4. 仅输出最终纯净 HTML 代码，不要附加任何 markdown 标记包裹！不要说任何废话！
"""

if len(st.session_state.messages) == 0:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

def delete_history_item(idx):
    if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "user":
        st.session_state.messages.pop(idx)
        if idx < len(st.session_state.messages) and st.session_state.messages[idx]["role"] == "assistant":
            st.session_state.messages.pop(idx)

# ==========================================
# 3. 侧边栏构建
# ==========================================
with st.sidebar:
    st.header("⚙️ 任务控制台")
    if st.button("🧹 清空当前录音与输入", use_container_width=True):
        st.session_state.draft_text_input = ""
        st.session_state.uploader_key += 1 
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

st.title("🚀 需求秒转 Demo 工具 (V5.0 终极抗压版)")

# ==========================================
# 4. 核心接口：音频转文字 (加入强大的自动重试机制)
# ==========================================
def transcribe_audio_to_text(audio_file):
    audio_bytes = audio_file.getvalue()
    max_retries = 3 # 最大重试次数
    
    for attempt in range(max_retries):
        try:
            transcript = whisper_client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=("audio.wav", audio_bytes), 
                response_format="text"
            )
            if hasattr(transcript, 'text'):
                return transcript.text
            return str(transcript)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2) # 失败后休息 2 秒，再次发起请求
                continue
            return f"【语音解析失败】: 免费接口当前排队人数过多，请再次点击提取按钮。详细报错: {str(e)}"

# ==========================================
# 5. 界面主布局：左右分栏
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
            with st.spinner("极速引擎正在提取语音 (若遇网络抖动会自动重试)..."):
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
            
            with st.spinner("AI 正在构建专业级前端组件中 (约需15-30秒)..."):
                try:
                    response = ds_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=st.session_state.messages,
                        temperature=0.2 
                    )
                    ai_result = response.choices[0].message.content
                    
                    # 【史诗级净化器】：剥离所有废话，提取纯净 HTML
                    html_match = re.search(r'(<!DOCTYPE html>.*</html>|<html.*</html>)', ai_result, re.DOTALL | re.IGNORECASE)
                    if html_match:
                        new_html = html_match.group(1).strip()
                    else:
                        new_html = ai_result.replace("```html", "").replace("```vue", "").replace("```", "").strip()
                    
                    st.session_state.html_code = new_html
                    st.session_state.messages.append({"role": "assistant", "content": "已生成代码"})
                    
                    # 触发状态：清空草稿、重置麦克风、开启撒花特效
                    st.session_state.need_clear_draft = True
                    st.session_state.uploader_key += 1 
                    st.session_state.show_success_effect = True
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"代码生成出错: {e}")

with col2:
    st.subheader("🖥️ 3. 交互 Demo")
    
    # 执行撒花特效
    if st.session_state.get("show_success_effect", False):
        st.balloons()
        st.session_state.show_success_effect = False # 阅后即焚

    if st.session_state.html_code:
        # 友好的成功提示语
        st.success("🎉 **生成完毕！** 代码已注入右侧面板，请直接在下方白框内点击交互。")
        st.caption("👇 若需要交付给研发或发给客户，可点击最下方的下载按钮。")
        
        # 渲染核心界面
        components.html(st.session_state.html_code, height=850, scrolling=True)
        
        st.markdown("---")
        st.download_button("⬇️ 导出完整 HTML 源文件", st.session_state.html_code, "demo_prototype.html", "text/html")
    else:
        st.info("👈 等待接收需求指令... (AI 响应后，预览画面将在此处直接渲染)")








