import io

import pdfplumber


def extract_text_from_pdf(content: bytes) -> str:
    """PDF bytes에서 텍스트 추출. 텍스트가 없으면 ValueError 발생."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("텍스트를 추출할 수 없습니다. 스캔 PDF이거나 텍스트가 없는 파일입니다.")
    return text
