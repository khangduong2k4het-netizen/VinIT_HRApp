"""Kết xuất hồ sơ demo ra DOCX và PDF.

Hai định dạng, cố ý khác nhau về bố cục để bộ demo có cảm giác "người thật gửi
lên" chứ không phải cùng một mẫu in ra hai lần:

* DOCX — bố cục CV hiện đại, tiêu đề màu, có gạch phân cách. Dùng ``python-docx``.
* PDF  — bố cục một cột kiểu CV in, phông DejaVu để giữ dấu tiếng Việt. Dùng
  ``reportlab``.

Cả hai đều mở đầu bằng **họ tên đầy đủ của ứng viên** trên dòng đầu tiên, đúng
như CV thật. Đây cũng là điều kiện để bộ trích xuất tên hoạt động: nếu dòng đầu
là một nhãn như "ỨNG VIÊN GIẢ" thì cả người đọc và model đều không biết đó là ai.

Chữ ký hàm nhận ``Candidate`` và trả về ``bytes`` để script gọi ghi ra tệp.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .cv_data import Candidate

#: Màu nhấn cho tiêu đề mục ở bản DOCX. Mỗi hồ sơ dùng cùng một tông để bộ demo
#: nhìn có tổ chức, nhưng đây là màu của "mẫu CV", không phải thông tin.
ACCENT = "1F4E5F"

#: Đường dẫn phông hỗ trợ dấu tiếng Việt cho bản PDF, thử lần lượt.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
)


def _find_fonts() -> tuple[str, str]:
    """Trả ``(regular, bold)``. Báo lỗi rõ nếu máy thiếu phông."""
    regular = next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)
    if not regular:
        raise RuntimeError(
            "Không tìm thấy phông DejaVu Sans. Cài gói fonts-dejavu-core "
            "hoặc trỏ biến DEMO_FONT_PATH tới một TTF có dấu tiếng Việt."
        )
    bold = str(Path(regular).with_name("DejaVuSans-Bold.ttf"))
    return regular, bold if Path(bold).exists() else regular


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def render_docx(candidate: Candidate) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()

    # Lề và phông mặc định: CV thật thường dày chữ hơn văn bản thường.
    for section in doc.sections:
        section.top_margin = Cm(1.6)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(1.9)
        section.right_margin = Cm(1.9)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)

    # Dòng đầu: họ tên đầy đủ. Cỡ lớn, không in hoa toàn bộ — CV thật ghi tên
    # đúng như giấy tờ, và hệ thống đọc lại đúng chuỗi này.
    name = doc.add_paragraph()
    name.paragraph_format.space_after = Pt(2)
    run = name.add_run(candidate.full_name)
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor.from_string(ACCENT)

    headline = doc.add_paragraph()
    headline.paragraph_format.space_after = Pt(2)
    hrun = headline.add_run(candidate.headline)
    hrun.font.size = Pt(11)
    hrun.italic = True

    contact = doc.add_paragraph()
    contact.paragraph_format.space_after = Pt(10)
    crun = contact.add_run(f"{candidate.email}  ·  {candidate.phone}")
    crun.font.size = Pt(9)

    def heading(text: str) -> None:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(10)
        para.paragraph_format.space_after = Pt(4)
        h = para.add_run(text.upper())
        h.bold = True
        h.font.size = Pt(10.5)
        h.font.color.rgb = RGBColor.from_string(ACCENT)

    def bullet(text: str) -> None:
        para = doc.add_paragraph(text, style="List Bullet")
        para.paragraph_format.space_after = Pt(2)
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    heading("Tóm tắt")
    doc.add_paragraph(candidate.summary)

    heading("Kinh nghiệm làm việc")
    for job in candidate.experience:
        line = doc.add_paragraph()
        line.paragraph_format.space_before = Pt(6)
        line.paragraph_format.space_after = Pt(0)
        role = line.add_run(job.role)
        role.bold = True
        line.add_run(" — ").font.size = Pt(10)
        line.add_run(job.company)

        meta = doc.add_paragraph()
        meta.paragraph_format.space_after = Pt(3)
        mrun = meta.add_run(f"{job.period}  ·  {job.location}")
        mrun.font.size = Pt(9)
        mrun.italic = True

        for text in job.bullets:
            bullet(text)

    heading("Học vấn")
    for edu in candidate.education:
        line = doc.add_paragraph()
        line.paragraph_format.space_after = Pt(0)
        line.add_run(edu.degree).bold = True
        line.add_run(f" — {edu.school}")
        meta = doc.add_paragraph()
        meta.paragraph_format.space_after = Pt(2)
        mrun = meta.add_run(edu.period)
        mrun.font.size = Pt(9)
        mrun.italic = True
        if edu.detail:
            doc.add_paragraph(edu.detail)

    heading("Kỹ năng")
    doc.add_paragraph(" · ".join(candidate.skills))

    if candidate.certifications:
        heading("Chứng chỉ")
        for cert in candidate.certifications:
            bullet(cert)

    if candidate.projects:
        heading("Dự án")
        for title, detail in candidate.projects:
            line = doc.add_paragraph()
            line.paragraph_format.space_after = Pt(0)
            line.add_run(title).bold = True
            doc.add_paragraph(detail)

    if candidate.languages:
        heading("Ngoại ngữ")
        doc.add_paragraph(" · ".join(candidate.languages))

    output = BytesIO()
    doc.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def render_pdf(candidate: Candidate) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        HRFlowable,
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    regular, bold = _find_fonts()
    pdfmetrics.registerFont(TTFont("CVSans", regular))
    pdfmetrics.registerFont(TTFont("CVSans-Bold", bold))

    accent = colors.HexColor("#" + ACCENT)
    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "CVName", parent=styles["Title"], fontName="CVSans-Bold",
        fontSize=19, leading=23, alignment=TA_LEFT, textColor=accent, spaceAfter=2,
    )
    headline_style = ParagraphStyle(
        "CVHeadline", parent=styles["Normal"], fontName="CVSans",
        fontSize=10.5, leading=14, spaceAfter=2,
    )
    contact_style = ParagraphStyle(
        "CVContact", parent=styles["Normal"], fontName="CVSans",
        fontSize=8.5, leading=12, textColor=colors.HexColor("#444444"), spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "CVSection", parent=styles["Normal"], fontName="CVSans-Bold",
        fontSize=10.5, leading=14, textColor=accent, spaceBefore=10, spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "CVBody", parent=styles["Normal"], fontName="CVSans",
        fontSize=9.5, leading=13, spaceAfter=3,
    )
    meta_style = ParagraphStyle(
        "CVMeta", parent=styles["Normal"], fontName="CVSans",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"), spaceAfter=3,
    )

    def escape(value: str) -> str:
        # Paragraph của reportlab hiểu một tập thẻ; CV có thể chứa & hoặc <.
        return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    story: list = []
    story.append(Paragraph(escape(candidate.full_name), name_style))
    story.append(Paragraph(escape(candidate.headline), headline_style))
    story.append(Paragraph(
        escape(f"{candidate.email} · {candidate.phone}"), contact_style))
    story.append(HRFlowable(width="100%", thickness=0.6, color=accent, spaceAfter=4))

    def section(title: str) -> None:
        story.append(Paragraph(escape(title.upper()), section_style))
        story.append(HRFlowable(width="100%", thickness=0.4,
                                color=colors.HexColor("#BBBBBB"), spaceAfter=4))

    def bullets(items) -> None:
        story.append(ListFlowable(
            [ListItem(Paragraph(escape(text), body_style), leftIndent=10) for text in items],
            bulletType="bullet", start="•", leftIndent=12, bulletFontName="CVSans",
            bulletFontSize=8,
        ))

    section("Tóm tắt")
    story.append(Paragraph(escape(candidate.summary), body_style))

    section("Kinh nghiệm làm việc")
    for job in candidate.experience:
        story.append(Paragraph(
            f"<b>{escape(job.role)}</b> — {escape(job.company)}", body_style))
        story.append(Paragraph(
            escape(f"{job.period} · {job.location}"), meta_style))
        bullets(job.bullets)
        story.append(Spacer(1, 4))

    section("Học vấn")
    for edu in candidate.education:
        story.append(Paragraph(
            f"<b>{escape(edu.degree)}</b> — {escape(edu.school)}", body_style))
        story.append(Paragraph(escape(edu.period), meta_style))
        if edu.detail:
            story.append(Paragraph(escape(edu.detail), body_style))

    section("Kỹ năng")
    story.append(Paragraph(escape(" · ".join(candidate.skills)), body_style))

    if candidate.certifications:
        section("Chứng chỉ")
        bullets(candidate.certifications)

    if candidate.projects:
        section("Dự án")
        for title, detail in candidate.projects:
            story.append(Paragraph(f"<b>{escape(title)}</b>", body_style))
            story.append(Paragraph(escape(detail), body_style))

    if candidate.languages:
        section("Ngoại ngữ")
        story.append(Paragraph(escape(" · ".join(candidate.languages)), body_style))

    output = BytesIO()
    SimpleDocTemplate(
        output, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.9 * cm, rightMargin=1.9 * cm,
        title=f"CV - {candidate.full_name}", author=candidate.full_name,
    ).build(story)
    return output.getvalue()
