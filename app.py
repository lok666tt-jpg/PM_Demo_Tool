import streamlit as st
from openai import OpenAI
import streamlit.components.v1 as components
import re
import time

# 1. 初始化大模型客户端 (用于需求提炼和代码生成)
API_KEY = "sk-8269c6bca93e4c57a4d4f0e3494550dc" # 👉 填入你的 Key
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="PM原型生成器 V4.0", layout="wide", initial_sidebar_state="collapsed")

st.title("🚀 需求秒转 Demo 工具 (V4.0 音频接入版)")

# ==========================================
# 🔌 核心模块：音频转文字 (预留给研发的私有化接口)
# ==========================================
def transcribe_audio_to_text(audio_file):
    """
    【研发交接文档】：
    这是语音转文字的核心接口。
    当前处于 PM 个人测试阶段，暂无私有化 ASR (语音识别) 服务。
    未来正式开发时，请替换此函数内部逻辑：
    - 方案A：接入公司内部私有部署的 Whisper 模型 (推荐 faster-whisper)
    - 方案B：接入公司采购的科大讯飞/阿里云私有化 ASR 接口
    
    输入：前端传入的音频文件对象
    输出：识别后的纯文本字符串
    """
    # ====== 下面是 PM 测试用的 Mock (模拟) 逻辑 ======
    # 模拟网络请求或模型处理的延迟
    time.sleep(2) 
    
    # 因为现在还没有接真实的语音模型，我们返回一段模拟的转录文本，方便你跑通后续的 Demo 生成流程
    mock_transcription = f"【系统模拟语音转录】：刚才开会确认了一下，在这个任务模块里，我希望主管进去能看到一个数据列表。点击‘派工’按钮，需要弹出一个对话框选择维修师傅，并能填写预计工时。填完保存，弹窗关闭。"
    
    return mock_transcription
    # ====== 上面是 PM 测试用的 Mock (模拟) 逻辑 ======

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
    st.subheader("🎤 1. 需求输入 (支持录音/文件)")
    
    # 增加选项卡：支持“文本直接输入”或“语音输入”
    input_mode = st.radio("选择输入方式：", ["⌨️ 文本输入", "🎙️ 录音/上传音频"], horizontal=True)
    
    user_input = ""
    
    if input_mode == "⌨️ 文本输入":
        user_input = st.chat_input("输入需求，例如：生成一个设备维保数据列表...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
    else:
        # 音频处理区
        st.info("提示：此处的音频处理已预留私有化接口。当前为模拟转录阶段。")
        
        # Streamlit 1.37+ 支持直接调用麦克风录音，或者上传文件
        audio_file = st.audio_input("直接录制你的需求")
        uploaded_file = st.file_uploader("或者上传会议录音 (mp3/wav)", type=['mp3', 'wav', 'm4a'])
        
        target_audio = audio_file or uploaded_file
        
        if target_audio:
            if st.button("🔄 开始转录并提取需求", type="primary"):
                with st.spinner("正在通过安全通道解析语音..."):
                    # 调用我们隔离出来的黑盒接口
                    transcribed_text = transcribe_audio_to_text(target_audio)
                    
                    st.success("✅ 转录成功！")
                    st.info(f"📄 转录内容：\n{transcribed_text}")
                    
                    # 将转录的文本自动作为用户的输入，推入大模型对话中
                    st.session_state.messages.append({"role": "user", "content": f"以下是会议录音转录内容，请据此生成/修改页面：\n{transcribed_text}"})
                    # 触发重新渲染以进入生成流程
                    st.rerun()

    # 渲染历史提问记录
    for msg in st.session_state.messages[1:]:
        if msg["role"] == "user":
            st.toast("已加载新需求") # 简化左侧显示，避免太长

    # 当有新需求加入时，触发大模型生成代码
    if st.session_state.messages[-1]["role"] == "user":
        with st.spinner("AI 正在构建前端组件中..."):
            try:
                response = client.chat.completions.create(
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
                st.error(f"生成出错: {e}")

with col2:
    st.subheader("🖥️ 2. 交互 Demo")
    # 彻底移除了源码查看，只保留纯净的演示界面
    if st.session_state.html_code:
        components.html(st.session_state.html_code, height=750, scrolling=True)
        st.download_button("⬇️ 下载 HTML", st.session_state.html_code, "demo_prototype.html", "text/html")
    else:
        st.info("👈 请在左侧输入需求或上传录音。")