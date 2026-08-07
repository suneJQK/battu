import streamlit as st
import os
import json
import glob
import asyncio
import re
from PIL import Image
from google import genai
from google.genai import types
import edge_tts

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="AI Luận Giải Bát Tự Tứ Trụ", page_icon="🔮", layout="wide")

st.title("🔮 Hệ Thống AI Đọc Lá Số & Luận Giải Bát Tự")
st.caption("Tự động phân tích ảnh lá số Tứ Trụ, tra cứu tri thức và đọc bài luận bằng nhiều giọng đọc AI.")

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
# 4. CHỌN GIỌNG ĐỌC AI (ĐA DẠNG VÙNG MIỀN)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("🎙️ Chọn Giọng Đọc AI")

# Tùy chọn các giọng đọc Microsoft Neural Voice Tiếng Việt
VOICE_OPTIONS = {
    "👩 Hoài Mỹ - Giọng Nữ Miền Bắc (Rõ ràng, truyền cảm)": "vi-VN-HoaiMyNeural",
    "👨 Nam Minh - Giọng Nam Miền Bắc (Trầm ấm, uy nghiêm)": "vi-VN-NamMinhNeural",
}

selected_voice_label = st.sidebar.selectbox(
    "Chọn giọng đọc muốn phát:",
    options=list(VOICE_OPTIONS.keys()),
    index=0
)

voice_code = VOICE_OPTIONS[selected_voice_label]

# ==========================================
# 5. LOAD DỮ LIỆU TRI THỨC TỪ OUTPUT_DATA
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
# 6. GIAO DIỆN TẢI LÊN LÁ SỐ & CÂU HỎI
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

if "result_text" not in st.session_state:
    st.session_state.result_text = ""

# ==========================================
# 7. QUÉT LÁ SỐ VÀ LUẬN GIẢI
# ==========================================
if st.button("🚀 Quét Lá Số & Thực Hiện Luận Giải", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ Chưa có API Key! Vui lòng vào Cấu hình Settings -> Secrets trên Streamlit Cloud để điền GEMINI_API_KEY.")
    elif uploaded_file is None:
        st.warning("⚠️ Vui lòng tải lên hình ảnh Lá Số Bát Tự!")
    else:
        with st.spinner("🔍 AI đang soi kỹ từng bảng lá số và tra cứu tri thức từ output_data..."):
            try:
                context_str = ""
                for i, item in enumerate(knowledge_base[:10], 1):
                    text_content = item.get('text') or item.get('messages') or item.get('output') or str(item)
                    context_str += f"--- DỮ LIỆU MẪU OUTPUT_DATA {i} ---\n{text_content}\n\n"

                prompt = f"""
Hãy đóng vai một Mắt Thần OCR chuyên gia phân tích lá số Tứ Trụ. 
Nhiệm vụ của bạn là soi kỹ HÌNH ẢNH LÁ SỐ BÁT TỰ và trích xuất KHÔNG BỎ SÓT BẤT KỲ BẢNG NÀO theo đúng cấu trúc sau:

### BƯỚC 1: TRÍCH XUẤT TOÀN BỘ BẢNG DỮ LIỆU CỦA LÁ SỐ
Hãy liệt kê rõ ràng các thông tin đọc được từ ảnh:
1. **Bảng Thông Tin Cá Nhân**: Họ tên, Giới tính, Âm Dương, Ngày/Tháng/Năm/Giờ sinh (Lịch Dương & Lịch Âm), Tiết khí, Nguyệt lệnh, Nhật chủ, Nạp Âm, Khởi vận.
2. **Bảng Tứ Trụ (Năm - Tháng - Ngày - Giờ)**:
   - Lịch Dương / Lịch Âm
   - Thiên Can / Địa Chi
   - Bát Tự / Nạp Âm / Ngũ Hành / Âm Dương
   - Thập Thần / Ý Nghĩa Thập Thần
   - Tàng Can / Phó Tinh / Thập Nhị Thần
3. **Bảng Đại Vận & Lưu Niên**:
   - Danh sách các Đại Vận (Ví dụ: Canh Tý 8-17t, Tân Sửu 18-27t, Nhâm Dần 28-37t,...).
   - Các năm Lưu Niên tương ứng.
4. **Bảng Thần Sát & Mệnh Cung**:
   - Thần Sát Nguyên Cục: Dương Nhẫn, Hồng Diễm, Tướng Tinh, Lộc Thần, Vong Thần,...
   - Mệnh Cung, Thai Nguyên, Niên Không, Nhật Không.

---

### BƯỚC 2: BÀI LUẬN GIẢI CHUYÊN SÂU
Dựa trên TOÀN BỘ dữ liệu đã trích xuất ở Bước 1 và CƠ SỞ TRÍ THỨC dưới đây để đưa ra bài luận giải:
- Phân tích chi tiết Nhật Chủ & sự vượng suy của Ngũ Hành.
- Phân tích tương quan Thập Thần (Thiên Tài, Chính Quan, Thiên Ấn, Kiếp Tài...).
- Luận giải ảnh hưởng của các Thần Sát (Dương Nhẫn, Lộc Thần, Vong Thần...).
- Phân tích Vận Hạn (Đại vận hiện tại và các năm Lưu Niên quan trọng).
- Lời khuyên định hướng.

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
                        temperature=0.1
                    )
                )

                st.session_state.result_text = response.text
                st.success("✅ Đã hoàn thành quét toàn bộ lá số và lập bài luận!")

            except Exception as e:
                st.error(f"❌ Đã xảy ra lỗi: {e}")

# ==========================================
# 8. HIỂN THỊ KẾT QUẢ & TẠO AUDIO THEO GIỌNG ĐỌC ĐÃ CHỌN
# ==========================================
if st.session_state.result_text:
    st.markdown("### 📋 KẾT QUẢ QUÉT LÁ SỐ & LUẬN GIẢI")
    st.write(st.session_state.result_text)

    st.markdown("---")
    st.subheader("🔊 Đọc bài luận bằng AI (Chọn giọng đọc)")
    st.info(f"Giọng đọc đang chọn: **{selected_voice_label}** (Thay đổi tại Thanh Cấu Hình bên trái)")

    if st.button("🎧 Tạo Audio với giọng đã chọn", type="primary"):
        with st.spinner("🎵 AI đang chuyển văn bản và ghép giọng đọc đầy đủ..."):
            try:
                # 1. Làm sạch ký tự đặc biệt/Markdown
                clean_text = (
                    st.session_state.result_text
                    .replace("*", "")
                    .replace("#", "")
                    .replace("- ", " ")
                    .replace("`", "")
                    .replace("|", " ")
                    .replace("\n\n", ". ")
                    .replace("\n", " ")
                )

                # 2. Tách nhỏ các câu theo dấu chấm
                raw_chunks = re.split(r'(?<=[.?!])\s+', clean_text)
                
                text_blocks = []
                current_block = ""
                for chunk in raw_chunks:
                    if len(current_block) + len(chunk) < 1000:
                        current_block += " " + chunk
                    else:
                        if current_block.strip():
                            text_blocks.append(current_block.strip())
                        current_block = chunk
                if current_block.strip():
                    text_blocks.append(current_block.strip())

                # 3. Hàm tạo audio bất đồng bộ với voice_code được chọn
                async def generate_full_audio():
                    full_audio_bytes = b""
                    for block in text_blocks:
                        if not block.strip():
                            continue
                        communicate = edge_tts.Communicate(block, voice_code)
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                full_audio_bytes += chunk["data"]
                    return full_audio_bytes

                # 4. Chạy tạo audio
                audio_data = asyncio.run(generate_full_audio())

                # 5. Phát trình đọc audio
                st.audio(audio_data, format="audio/mp3")
                st.success(f"✅ Đã tạo giọng đọc **{selected_voice_label}** thành công! Bấm Play để nghe.")

            except Exception as e:
                st.error(f"❌ Lỗi tạo Audio: {e}")
