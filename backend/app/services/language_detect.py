"""Dò ngôn ngữ của nội dung JD, để không phải hỏi HR một câu vô nghĩa.

Bối cảnh: trước đây màn tạo vị trí có ô "Ngôn ngữ JD" (English / Tiếng Việt).
Ô đó **không ảnh hưởng gì tới kết quả** — giá trị chỉ được ghi vào
``jd_versions.language_code`` rồi đọc ra để hiện lại, không nơi nào dùng để
quyết định cách sinh tiêu chí hay cách chấm điểm (prompt vốn đã dặn LLM tự
nhận biết ngôn ngữ từ nội dung). Một ô nhập trông như đang điều khiển hệ thống
mà thực ra không điều khiển gì còn tệ hơn không có ô nào, vì HR tin nhầm.

Nay ngôn ngữ được suy ra từ chính nội dung. Hàm này chỉ làm một việc: đếm dấu
tiếng Việt. Không dùng thư viện nhận dạng ngôn ngữ vì:

* Chỉ cần phân biệt Việt với "còn lại", mà JD tiếng Anh là mặc định.
* Thư viện ngoài thêm một phụ thuộc và một chỗ có thể hỏng, cho một bài toán
  mà đếm dấu đã giải quyết đúng.

Giới hạn đã biết: văn bản tiếng Việt **không dấu** ("Tuyen dung ky su phan
mem") sẽ bị đoán là tiếng Anh. Chấp nhận: JD thật gần như luôn có dấu, và đoán
sai ở đây chỉ ảnh hưởng tới nhãn lưu trong DB, không ảnh hưởng tới nội dung
tiêu chí — LLM vẫn đọc nguyên văn JD.
"""
from __future__ import annotations

#: Các ký tự chỉ có trong tiếng Việt có dấu. Không liệt kê nguyên âm trần
#: (a, e, o, u, i, y) vì chúng có trong mọi ngôn ngữ dùng Latin.
_VIETNAMESE_LETTERS = frozenset(
    "ăâđêôơư"
    "ĂÂĐÊÔƠƯ"
    "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
    "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    "ÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊ"
    "ÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ"
)

#: Tỉ lệ chữ cái có dấu để coi là tiếng Việt. Ngưỡng lấy từ đo thật:
#:
#: * JD tiếng Việt thật: 0,17 – 0,29 (ba mẫu, đều trên 17%).
#: * JD tiếng Anh có trích dẫn tiếng Việt ("Đại học Bách khoa Hà Nội",
#:   "Hanoi"): 0,024.
#:
#: 0,08 nằm giữa hai nhóm, cách cả hai phía hơn ba lần. Đặt thấp hơn (0,005)
#: từng làm JD tiếng Anh bị gắn nhãn tiếng Việt chỉ vì một tên trường.
_MIN_DIACRITIC_SHARE = 0.08
#: Chặn thêm bằng số tuyệt đối: văn bản 30 chữ mà có 3 dấu vẫn chưa đủ căn cứ.
_MIN_DIACRITIC_COUNT = 5


def detect_language_code(text: str | None) -> str:
    """Trả ``'vi'`` hoặc ``'en'``. Không bao giờ ném lỗi."""
    if not text:
        return "en"
    letters = 0
    marked = 0
    for char in text:
        if char.isalpha():
            letters += 1
            if char in _VIETNAMESE_LETTERS:
                marked += 1
    if letters == 0:
        return "en"
    # Ngưỡng tuyệt đối quan trọng với văn bản ngắn: một tiêu đề 20 chữ có 1 dấu
    # không đủ để gọi cả JD là tiếng Việt.
    if marked < _MIN_DIACRITIC_COUNT:
        return "en"
    return "vi" if marked / letters >= _MIN_DIACRITIC_SHARE else "en"
