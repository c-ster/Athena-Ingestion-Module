import PyPDF2
import docx
from bs4 import BeautifulSoup

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a PDF file."""
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = "".join(page.extract_text() for page in reader.pages)
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extracts text from a DOCX file."""
    doc = docx.Document(file_path)
    text = "\n".join(para.text for para in doc.paragraphs)
    return text

def extract_text_from_txt(file_path: str) -> str:
    """Extracts text from a TXT file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    return text

def extract_text_from_html(file_path: str) -> str:
    """Extracts text from an HTML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        return soup.get_text()

def extract_text_from_xml(file_path: str) -> str:
    """Extracts text from an XML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')
        return soup.get_text()
