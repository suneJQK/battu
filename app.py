import streamlit as st
import os
import json
import glob
from PIL import Image
from google import genai
from google.genai import types
from gtts import gTTS
import io

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="AI Luận Giải Bát Tự Tứ Trụ", page_icon="🔮", layout="wide")

st.title("🔮 Hệ Thống AI Đọc Lá Số & Luận Giải Bát Tự")
st.caption("Tự động phân tích ảnh lá số Tứ Trụ, tra cứu tri thức và đọc bài luận bằng giọng nói AI.")

# ==========================================
# 1. TỰ ĐỘNG ĐỌC BẢO MẬT GEMINI API KEY
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# ==========================================
# 2. ĐỌC FILE SYSTEM PROMPT TỪ THƯ MỤC DATA
# ==========================================
def load_system_prompt():
    prompt_path = os.path.join("data", "system_prompt.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return (
        "Bạn là một chuyên gia luận giải Bát Tự Tứ Trụ và Mệnh Lý học cao cấp.\n"
        "Nhiệm vụ của bạn là đọc lá số và tra cứu tri thức trong file dữ liệu được cung cấp để đưa ra lời luận giải chính xác."
    )

# ==========================================
# 3. THANH CẤU HÌNH BÊN TRÁI (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Cấu Hình Hệ Thống")

# Hiển thị trạng thái kết nối Key
if api_key:
    st.sidebar.success("🔑 API Key: ĐÃ KẾT NỐI (Streamlit Secrets)")
else:
    st.sidebar.error("⚠️ Chưa tìm thấy GEMINI_API_KEY trong Streamlit Secrets!")

st.sidebar.markdown("---")

default_prompt = load_system_prompt()
system_prompt_input = st.sidebar.text_area(
    "🎯 System Prompt (Đọc từ data/system_prompt.txt):",
    value=default_prompt,
    height=200
)

# ==========================================
# 4. LOAD DỮ LIỆU TRI THỨC TỪ OUTPUT_DATA
# ==========================================
@st.cache_data
def load_knowledge_base():
    jsonl_files = glob.glob("output_data/**/*.jsonl", recursive=True) + glob.glob("output_data/*.jsonl")
    
    if not jsonl_files:
        jsonl_files = glob.glob("**/*.jsonl", recursive=True)

    if not jsonl_files:
        return []
    
    latest_file = max(jsonl_files, key=os.path.getmtime)
    data = []
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line.strip()))
    except Exception as e:
        st.error(f"Lỗi đọc file {latest_file}: {e}")
    return data

knowledge_base = load_knowledge_base()

if knowledge_base:
    st.sidebar.success(f"📚 Đã nạp {len(knowledge_base)} mẫu dữ liệu từ `output_data`!")
else:
    st.sidebar.error("❌ Chưa thấy file .jsonl trong thư mục `output_data`!")

# ==========================================
# 5. GIAO DIỆN TẢI LÊN LÁ SỐ & CÂU HỎI
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 1. Tải lên ảnh Lá Số Bát Tự")
    uploaded_file = st.file_uploader("Chọn ảnh lá số (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])
    
    image = None
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Lá số Bát Tự đã tải lên", use_container_width=True)

with col2:
    st.subheader("📝 2. Yêu cầu / Cần luận giải chi tiết")
    user_query = st.text_area(
        "Nhập thắc mắc hoặc nội dung muốn tập trung luận giải:",
        height=140,
        placeholder="Ví dụ: Luận giải tổng quan công danh, tài lộc, gia đạo và các vận hạn lớn của lá số này..."
    )

st.markdown("---")

# Quản lý trạng thái lưu kết quả bài luận để chuyển thành Audio
if "result_text" not in st.session_state:
    st.session_state.result_text = ""

# ==========================================
# 6. QUÉT LÁ SỐ VÀ LUẬN GIẢI
# ==========================================
if st.button("🚀 Quét Lá Số & Thực Hiện Luận Giải", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ Chưa có API Key! Vui lòng vào Cấu hình Settings -> Secrets trên Streamlit Cloud để điền GEMINI_API_KEY.")
    elif uploaded_file is None:
        st.warning("⚠️ Vui lòng tải lên hình ảnh Lá Số Bát Tự!")
    else:
        with st.spinner("🔍 AI đang mắt thần quét lá số và tra cứu tri thức từ thư mục output_data..."):
            try:
                context_str = ""
                for i, item in enumerate(knowledge_base[:10], 1):
                    text_content = item.get('text') or item.get('messages') or item.get('output') or str(item)
                    context_str += f"--- DỮ LIỆU MẪU OUTPUT_DATA {i} ---\n{text_content}\n\n"

                prompt = f"""
Nhiệm vụ của bạn:
1. Quét hình ảnh Lá số Bát Tự được đính kèm và trích xuất thông tin:
   - Thông tin cá nhân, Tứ trụ (Năm, Tháng, Ngày, Giờ), Can Chi, Tàng Can, Thập Thần, Đại Vận, Thần Sát.

2. LUẬN GIẢI MỆNH LÝ CHUYÊN SÂU:
   Sử dụng thông tin lá số ĐỒNG THỜI tra cứu và vận dụng CƠ SỞ DỮ LIỆU TÀI LIỆU được trích xuất từ `output_data` dưới đây để phân tích:
   - Sức mạnh Nhật Chủ, Ngũ Hành khuyết thiếu/vượng.
   - Ý nghĩa Thập Thần và tương quan lá số.
   - Luận giải Vận Hạn (Đại vận, Lưu niên).
   - Lời khuyên ứng biến.

CƠ SỞ DỮ LIỆU TRÍ THỨC (TRÍCH XUẤT TỪ OUTPUT_DATA):
==================================================
{context_str}
==================================================

YÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG:
{user_query if user_query.strip() else 'Hãy luận giải tổng quan toàn bộ lá số này.'}
"""

                client = genai.Client(api_key=api_key)
                
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt_input,
                        temperature=0.2
                    )
                )

                st.session_state.result_text = response.text
                st.success("✅ Đã hoàn thành quét lá số và luận giải!")

            except Exception as e:
                st.error(f"❌ Đã xảy ra lỗi: {e}")

# ==========================================
# 7. HIỂN THỊ KẾT QUẢ & ĐỌC AUDIO TỰ ĐỘNG
# ==========================================
if st.session_state.result_text:
    st.markdown("### 📋 KẾT QUẢ QUÉT LÁ SỐ & LUẬN GIẢI")
    st.write(st.session_state.result_text)

    st.markdown("---")
    st.subheader("🔊 Đọc bài luận bằng AI (Audio)")

    if st.button("🎧 Tạo giọng đọc Audio (Tiếng Việt)"):
        with st.spinner("🎵 AI đang chuyển bài luận thành giọng đọc âm thanh..."):
            try:
                # Làm sạch ký tự Markdown (*, #, -) để giọng đọc tự nhiên
                clean_text = st.session_state.result_text.replace("*", "").replace("#", "").replace("-", "")
                
                # Giới hạn độ dài ngắn gọn nếu bài quá dài để xử lý nhanh hơn
                tts = gTTS(text=clean_text[:3000], lang='vi', slow=False)
                
                # Lưu vào bộ nhớ đệm
                sound_file = io.BytesIO()
                tts.write_to_fp(sound_file)
                sound_file.seek(0)

                # Trình phát audio
                st.audio(sound_file, format="audio/mp3")
                st.success("✅ Tạo file giọng đọc thành công! Nhấn Nút Play bên trên để nghe.")
            except Exception as e:
                st.error(f"Lỗi tạo Audio: {e}")
