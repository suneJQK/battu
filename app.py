import streamlit as st
import os
import json
import glob
from PIL import Image
from google import genai
from google.genai import types

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="AI Luận Giải Bát Tự Tứ Trụ", page_icon="🔮", layout="wide")

st.title("🔮 Hệ Thống AI Đọc Lá Số & Luận Giải Bát Tự")
st.caption("Tự động phân tích ảnh lá số Tứ Trụ và tra cứu tài liệu chuyên ngành để đưa ra lời luận giải.")

# ==========================================
# 1. TỰ ĐỘNG ĐỌC BẢO MẬT GEMINI API KEY
# ==========================================
# Đọc API Key bảo mật từ Streamlit Secrets (trên Cloud) hoặc Environment Variable (Local)
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# ==========================================
# 2. THANH CẤU HÌNH BÊN TRÁI (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Cấu Hình Hệ Thống")

# Hiển thị trạng thái kết nối Key (không làm lộ mã Key)
if api_key:
    st.sidebar.success("🔑 Trạng thái API Key: ĐÃ KẾT NỐI (Streamlit Secrets)")
else:
    st.sidebar.error("⚠️ Chưa tìm thấy GEMINI_API_KEY trong Streamlit Secrets!")

st.sidebar.markdown("---")

# Prompt điều hướng AI
default_system_prompt = (
    "Bạn là một chuyên gia luận giải Bát Tự Tứ Trụ và Mệnh Lý học cao cấp.\n"
    "Nhiệm vụ của bạn:\n"
    "1. Đọc và trích xuất TOÀN BỘ thông tin lá số Bát Tự từ hình ảnh (Tứ trụ: Năm, Tháng, Ngày, Giờ; Can Chi, Tàng Can, Nạp Âm, Thập Thần, Đại Vận, Thần Sát,...).\n"
    "2. Kết hợp với CƠ SỞ TRÍ THỨC tài liệu được cung cấp để phân tích, luận giải chi tiết về Mệnh chủ.\n"
    "3. Quy tắc BẮT BUỘC: Bám sát tài liệu nguồn. Nếu có thuật ngữ trong lá số, hãy dùng tri thức tài liệu để giải thích ý nghĩa."
)

system_prompt_input = st.sidebar.text_area(
    "🎯 System Prompt (Định hướng AI):",
    value=default_system_prompt,
    height=220
)

# ==========================================
# 3. LOAD DỮ LIỆU TÀI LIỆU NGUỒN (THƯ MỤC DATA)
# ==========================================
@st.cache_data
def load_knowledge_base():
    # Quét các file .jsonl trong thư mục data (hoặc dự phòng toàn bộ dự án)
    jsonl_files = glob.glob("data/**/*.jsonl", recursive=True) + glob.glob("data/*.jsonl")
    
    # Ưu tiên lấy file rag_chunks (bỏ qua file finetune nếu có)
    rag_files = [f for f in jsonl_files if "finetune" not in f]
    target_files = rag_files if rag_files else jsonl_files

    if not target_files:
        target_files = glob.glob("**/*.jsonl", recursive=True)

    if not target_files:
        return []
    
    latest_file = max(target_files, key=os.path.getmtime)
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
    st.sidebar.success(f"📚 Đã nạp {len(knowledge_base)} đoạn tri thức từ thư mục `data`!")
else:
    st.sidebar.error("❌ Chưa thấy file .jsonl trong thư mục `data`!")

# ==========================================
# 4. MỤC TẢI LÊN LÁ SỐ & CÂU HỎI
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
    st.subheader("📝 2. Yêu cầu/Câu hỏi bổ sung")
    user_query = st.text_area(
        "Nhập thắc mắc hoặc nội dung muốn tập trung luận giải:",
        height=140,
        placeholder="Ví dụ: Luận giải tổng quan công danh, tài lộc, gia đạo và các vận hạn lớn của lá số này..."
    )

st.markdown("---")

# ==========================================
# 5. QUÉT LÁ SỐ VÀ LUẬN GIẢI
# ==========================================
if st.button("🚀 Quét Lá Số & Thực Hiện Luận Giải", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ Chưa có API Key! Vui lòng vào Cấu hình Settings -> Secrets trên Streamlit Cloud để điền GEMINI_API_KEY.")
    elif uploaded_file is None:
        st.warning("⚠️ Vui lòng tải lên hình ảnh Lá Số Bát Tự!")
    else:
        with st.spinner("🔍 AI đang mắt thần quét lá số và tra cứu tri thức tài liệu..."):
            try:
                # Chuẩn bị tri thức tài liệu đính kèm
                context_str = ""
                for i, chunk in enumerate(knowledge_base[:10], 1):
                    context_str += f"--- TRÍ THỨC TÀI LIỆU {i} ({chunk.get('context', 'Chung')}) ---\n"
                    context_str += f"{chunk.get('text', '')}\n\n"

                # Xây dựng Prompt tổng hợp
                prompt = f"""
Nhiệm vụ:
1. Hãy quét kỹ hình ảnh Lá số Bát Tự được đính kèm và đọc ra đầy đủ các thông tin:
   - Thông tin cá nhân (Họ tên, Giới tính, Ngày giờ sinh, Âm/Dương lịch, Mệnh Nạp âm).
   - Tứ Trụ (Năm, Tháng, Ngày, Giờ): Can Chi, Nạp Âm, Thập Thần, Tàng Can, Phó Tinh, Thập Nhị Thần.
   - Các Đại Vận, Lưu Niên và Thần Sát (Dương Nhẫn, Hồng Diễm, Vong Thần,...).

2. BÀI LUẬN GIẢI CHUYÊN SÂU:
   Dựa trên lá số đã quét ĐỒNG THỜI tra cứu CƠ SỞ TRÍ THỨC dưới đây để luận giải chi tiết:
   - Phân tích Nhật Chủ và sức mạnh Ngũ Hành.
   - Phân tích Ý nghĩa Thập Thần (Chính Quan, Thiên Tài, Thiên Ấn,...).
   - Đánh giá các Vận Hạn (Đại Vận / Lưu Niên).
   - Đưa ra Lời khuyên định hướng.

CƠ SỞ TRÍ THỨC TÀI LIỆU NGUỒN TÌM THẤY:
==================================================
{context_str}
==================================================

YÊU CẦU BỔ SUNG CỦA NGƯỜI DÙNG:
{user_query if user_query.strip() else 'Hãy luận giải tổng quan toàn bộ lá số này.'}
"""

                # Gọi Gemini API bảo mật
                client = genai.Client(api_key=api_key)
                
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt_input,
                        temperature=0.2
                    )
                )

                st.success("✅ Đã hoàn thành quét lá số và luận giải!")
                st.markdown("### 📋 KẾT QUẢ QUÉT LÁ SỐ & LUẬN GIẢI")
                st.write(response.text)

            except Exception as e:
                st.error(f"❌ Đã xảy ra lỗi: {e}")
