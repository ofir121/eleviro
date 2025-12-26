import io
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
from fastapi import UploadFile

async def parse_pdf(file: UploadFile) -> str:
    content = await file.read()
    pdf_file = io.BytesIO(content)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

async def parse_docx(file: UploadFile) -> str:
    content = await file.read()
    docx_file = io.BytesIO(content)
    doc = Document(docx_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def scrape_url(url: str) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:10000] # Limit to 10k chars to avoid token limits
    except Exception as e:
        print(f"Error scraping URL: {e}")
        return ""
