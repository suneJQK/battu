import asyncio
import base64
from datetime import datetime
import glob
import json
import os
import re
from google import genai
from google.genai import types
import edge_tts
from PIL import Image
import requests
import streamlit as st

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="AI Luận Giải Bát Tự Tứ Trụ", page_icon="🔮", layout="wide"
)

st.title("🔮 Hệ Thống AI Đọc Lá Số & Luận Giải Bát Tự")
st.caption(
    "Tự động phân tích ảnh lá số Tứ Trụ, lưu trữ ảnh lên GitHub, tra cứu tri"
    " thức và đọc bài luận bằng nhiều giọng đọc AI."
)

# ==========================================
# 1. TỰ ĐỘNG ĐỌC BẢO MẬT GEMINI & GITHUB API KEYS
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
github_token = st.secrets.get(
    "GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", "")
)
github_repo = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))
github_branch = st.secrets.get(
    "GITHUB_BRANCH", os.environ.get("GITHUB_BRANCH", "main")
)


# ==========================================
# 2. HÀM TẢI ẢNH LÊN GITHUB REPOSITORY
# ==========================================
def upload_image_to_github(image_bytes, filename):
  """Hàm upload byte dữ liệu của ảnh lên GitHub repository qua REST API v3."""
  if not github_token or not github_repo:
    return (
        False,
        "⚠️ Chưa cấu hình GITHUB_TOKEN hoặc GITHUB_REPO trong Secrets!",
    )

  try:
    # Tạo tên file duy nhất theo thời gian để tránh trùng lặp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_filename = re.sub(r"[^\w\.-]", "_", filename)
    file_path = f"uploaded_images/{timestamp}_{clean_filename}"

    url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"

    # Mã hóa dữ liệu ảnh sang Base64
    encoded_content = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    payload = {
        "message": f"Upload lá số bát tự: {clean_filename}",
        "content": encoded_content,
        "branch": github_branch,
    }

    response = requests.put(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
      res_data = response.json()
      raw_url = res_data.get("content", {}).get("html_url", "")
      return True, raw_url
    else:
      error_msg = response.json().get("message", response.text)
      return False, f"Lỗi GitHub API ({response.status_code}): {error_msg}"
  except Exception as e:
    return False, f"Lỗi kết nối GitHub: {e}"


# ==========================================
# 3. ĐỌC FILE SYSTEM PROMPT TỪ THƯ MỤC DATA
# ==========================================
def load_system_prompt():
  prompt_path = os.path.join("data", "system_prompt.txt")
  if os.path.exists(prompt_path):
    with open(prompt_path, "r", encoding="utf-8") as f:
      return f.read().strip()
  return (
      "Bạn là một chuyên gia luận giải Bát Tự Tứ Trụ và Mệnh Lý học cao"
      " cấp.\nNhiệm vụ của bạn là đọc lá số và tra cứu tri thức trong file dữ"
      " liệu được cung cấp để đưa ra lời luận giải chính xác."
  )


# ==========================================
# 4. THANH CẤU HÌNH BÊN TRÁI (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Cấu Hình Hệ Thống")

# Hiển thị trạng thái kết nối Gemini Key
if api_key:
  st.sidebar.success("🔑 Gemini API Key: ĐÃ KẾT NỐI")
else:
  st.sidebar.error("⚠️ Chưa tìm thấy GEMINI_API_KEY!")

# Hiển thị trạng thái kết nối GitHub
if github_token and github_repo:
  st.sidebar.success(f"🐙 GitHub Sync: ĐÃ KẾT NỐI ({github_repo})")
else:
  st.sidebar.warning("⚠️ GitHub Sync: Chưa cấu hình Token/Repo (Không bắt buộc)")

st.sidebar.markdown("---")

default_prompt = load_system_prompt()
system_prompt_input = st.sidebar.text_area(
    "🎯 System Prompt (Đọc từ data/system_prompt.txt):",
    value=default_prompt,
    height=200,
)

# ==========================================
# 5. CHỌN GIỌNG ĐỌC AI
# ==========================================
st.sidebar.markdown("---")
st.sidebar.header("🎙️ Chọn Giọng Đọc AI")

VOICE_OPTIONS = {
    "👩 Hoài Mỹ - Giọng Nữ Miền Bắc": "vi-VN-HoaiMyNeural",
    "👨 Nam Minh - Giọng Nam Miền Bắc": "vi-VN-NamMinhNeural",
}

selected_voice_label = st.sidebar.selectbox(
    "Chọn giọng đọc muốn phát:", options=list(VOICE_OPTIONS.keys()), index=0
)

voice_code = VOICE_OPTIONS[selected_voice_label]


# ==========================================
# 6. LOAD DỮ LIỆU TRI THỨC TỪ OUTPUT_DATA
# ==========================================
@st.cache_data
def load_knowledge_base():
  jsonl_files = glob.glob(
      "output_data/**/*.jsonl", recursive=True
  ) + glob.glob("output_data/*.jsonl")

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
  st.sidebar.success(
      f"📚 Đã nạp {len(knowledge_base)} mẫu dữ liệu từ `output_data`!"
  )
else:
  st.sidebar.error("❌ Chưa thấy file .jsonl trong thư mục `output_data`!")

# ==========================================
# 7. GIAO DIỆN TẢI LÊN LÁ SỐ & CÂU HỎI
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
  st.subheader("📸 1. Tải lên ảnh Lá Số Bát Tự")
  uploaded_file = st.file_uploader(
      "Chọn ảnh lá số (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"]
  )

  image = None
  if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(
        image, caption="Lá số Bát Tự đã tải lên", use_container_width=True
    )

with col2:
  st.subheader("📝 2. Yêu cầu / Cần luận giải chi tiết")
  user_query = st.text_area(
      "Nhập thắc mắc hoặc nội dung muốn tập trung luận giải:",
      height=140,
      placeholder=(
          "Ví dụ: Luận giải tổng quan công danh, tài lộc, gia đạo và các vận hạn"
          " lớn của lá số này..."
      ),
  )

st.markdown("---")

if "result_text" not in st.session_state:
  st.session_state.result_text = ""

# ==========================================
# 8. QUÉT LÁ SỐ, LƯU GITHUB VÀ LUẬN GIẢI
# ==========================================
if st.button(
    "🚀 Quét Lá Số & Thực Hiện Luận Giải",
    type="primary",
    use_container_width=True,
):
  if not api_key:
    st.error(
        "❌ Chưa có API Key! Vui lòng vào Cấu hình Settings -> Secrets trên"
        " Streamlit Cloud để điền GEMINI_API_KEY."
    )
  elif uploaded_file is None:
    st.warning("⚠️ Vui lòng tải lên hình ảnh Lá Số Bát Tự!")
  else:
    # ----------------------------------------------------
    # BƯỚC PHỤ: TỰ ĐỘNG UPLOAD ẢNH LÊN GITHUB REPOSITORY
    # ----------------------------------------------------
    if github_token and github_repo:
      with st.spinner("📤 Đang tự động sao lưu ảnh lá số lên GitHub..."):
        # Reset con trỏ file để đọc bytes
        uploaded_file.seek(0)
        img_bytes = uploaded_file.read()
        success, gh_res = upload_image_to_github(img_bytes, uploaded_file.name)

        if success:
          st.success(f"📦 Đã lưu ảnh thành công lên GitHub! [Xem file]({gh_res})")
        else:
          st.warning(f"⚠️ Lưu GitHub thất bại: {gh_res}")

    # ----------------------------------------------------
    # QUY TRÌNH LUẬN GIẢI BÁT TỰ BẰNG GEMINI
    # ----------------------------------------------------
    with st.spinner(
        "🔍 AI đang soi kỹ từng bảng lá số và tra cứu tri thức từ"
        " output_data..."
    ):
      try:
        context_str = ""
        for i, item in enumerate(knowledge_base[:10], 1):
          text_content = (
              item.get("text")
              or item.get("messages")
              or item.get("output")
              or str(item)
          )
          context_str += (
              f"--- DỮ LIỆU MẪU OUTPUT_DATA {i} ---\n{text_content}\n\n"
          )

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

### BƯỚC 2: BÀI LUẬN GIẢI CHUYÊN SÂU THEO HỆ THỐNG MANH PHÁI
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
                system_instruction=system_prompt_input, temperature=0.1
            ),
        )

        st.session_state.result_text = response.text
        st.success("✅ Đã hoàn thành quét toàn bộ lá số và lập bài luận!")

      except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi: {e}")

# ==========================================
# 9. HIỂN THỊ KẾT QUẢ & ĐỌC AUDIO (BỎ QUA BƯỚC 1)
# ==========================================
if st.session_state.result_text:
  st.markdown("### 📋 KẾT QUẢ QUÉT LÁ SỐ & LUẬN GIẢI")
  st.write(st.session_state.result_text)

  st.markdown("---")
  st.subheader("🔊 Đọc bài luận bằng AI (Chỉ đọc BƯỚC 2)")
  st.info(
      f"Giọng đọc đang chọn: **{selected_voice_label}** | 💡 **Chế độ:** Bỏ qua"
      " Bước 1 trích xuất bảng, chỉ đọc phần bài luận chuyên sâu."
  )

  if st.button("🎧 Tạo Audio bài luận (Bắt đầu từ Bước 2)", type="primary"):
    with st.spinner("🎵 AI đang lọc nội dung Bước 2 và tạo giọng đọc..."):
      try:
        full_text = st.session_state.result_text

        # 1. Thuật toán tự động cắt phần BƯỚC 2 (Bỏ qua Bước 1)
        buec2_keyword = "BƯỚC 2"
        if buec2_keyword in full_text.upper():
          start_index = full_text.upper().find(buec2_keyword)
          step2_text = full_text[start_index:]
        else:
          step2_text = full_text

        # 2. Làm sạch văn bản (Loại bỏ các ký tự Markdown)
        clean_text = (
            step2_text.replace("*", "")
            .replace("#", "")
            .replace("- ", " ")
            .replace("`", "")
            .replace("|", " ")
            .replace("\n\n", ". ")
            .replace("\n", " ")
        )

        # 3. Tách nhỏ văn bản thành các câu để truyền tải mượt mà
        raw_chunks = re.split(r"(?<=[.?!])\s+", clean_text)

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

        # 4. Hàm gọi Edge-TTS ghép nối các đoạn Audio
        async def generate_step2_audio():
          full_audio_bytes = b""
          for block in text_blocks:
            if not block.strip():
              continue
            communicate = edge_tts.Communicate(block, voice_code)
            async for chunk in communicate.stream():
              if chunk["type"] == "audio":
                full_audio_bytes += chunk["data"]
          return full_audio_bytes

        # 5. Chạy lệnh bất đồng bộ
        audio_data = asyncio.run(generate_step2_audio())

        # 6. Xuất trình phát Audio
        st.audio(audio_data, format="audio/mp3")
        st.success(
            "✅ Đã tạo giọng đọc BƯỚC 2 thành công! Bấm nút Play để bắt đầu"
            " nghe bài luận."
        )

      except Exception as e:
        st.error(f"❌ Lỗi tạo Audio: {e}")
