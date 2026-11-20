"""Dò ngôn ngữ JD: chỉ cần phân biệt tiếng Việt với phần còn lại."""
import pytest

from app.services.language_detect import detect_language_code


@pytest.mark.parametrize('text', [
    'Senior Backend Engineer. 5+ years of Python and PostgreSQL experience.',
    'We offer competitive salary, health insurance, and 15 days of leave.',
    'VINFAST | DATA ENGINEER — Hanoi, Vietnam',
])
def test_english_jd_is_english(text):
    assert detect_language_code(text) == 'en'


@pytest.mark.parametrize('text', [
    'Kỹ sư phần mềm Backend. Yêu cầu 5 năm kinh nghiệm với Python và PostgreSQL.',
    'Chúng tôi cung cấp mức lương cạnh tranh, bảo hiểm sức khỏe và 15 ngày phép năm.',
    'Mô tả công việc: phát triển hệ thống tuyển dụng, phối hợp với bộ phận nhân sự.',
])
def test_vietnamese_jd_is_vietnamese(text):
    assert detect_language_code(text) == 'vi'


def test_english_jd_with_a_few_vietnamese_words_stays_english():
    """Trích dẫn tên trường/địa danh tiếng Việt không biến JD thành tiếng Việt.

    Đây là ca dễ sai nhất: JD tiếng Anh hay nhắc "Đại học Bách khoa Hà Nội".
    Nếu chỉ cần một chữ có dấu là kết luận 'vi' thì gần như mọi JD ở Việt Nam
    đều bị gắn nhãn sai.
    """
    long_english = (
        'We are hiring a Senior Backend Engineer to build our recruitment platform. '
        'You will work with Python, PostgreSQL and Redis. Partner universities include '
        'Đại học Bách khoa Hà Nội. You will report to the Head of Engineering and '
        'collaborate with a team of eight engineers across Hanoi and Ho Chi Minh City.'
    )
    assert detect_language_code(long_english) == 'en'


def test_mixed_jd_with_majority_vietnamese_is_vietnamese():
    mixed = (
        'Mô tả công việc: phát triển dịch vụ backend bằng Python. '
        'Yêu cầu kinh nghiệm với PostgreSQL, Redis và hệ thống phân tán. '
        'Chúng tôi làm việc tại Hà Nội, thời gian linh hoạt. '
        'Nice to have: Kubernetes.'
    )
    assert detect_language_code(mixed) == 'vi'


@pytest.mark.parametrize('text', ['', None, '   ', '12345 !@#$%', 'x'])
def test_degenerate_input_never_raises(text):
    """Không bao giờ ném lỗi, mặc định tiếng Anh (mặc định của hệ thống)."""
    assert detect_language_code(text) == 'en'


def test_short_vietnamese_heading_alone_is_not_enough():
    """Một tiêu đề ngắn có vài dấu thì chưa đủ căn cứ — thà mặc định English."""
    assert detect_language_code('Kỹ sư Backend') == 'en'
