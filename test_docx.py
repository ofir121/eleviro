import asyncio
from app.utils.parsers import parse_docx, clean_resume_text, extract_contact_from_text, parse_resume_text_to_structure
from app.utils.formatters import build_markdown_resume

class MockUploadFile:
    def __init__(self, path, filename):
        self.path = path
        self.filename = filename
    async def read(self):
        with open(self.path, 'rb') as f:
            return f.read()

async def main():
    file = MockUploadFile("Ofir Shliefer CV Master 2026.docx", "Ofir Shliefer CV Master 2026.docx")
    res = await parse_docx(file)
    
    md = build_markdown_resume(res, extract_contact_from_text(res.full_text), "Ofir Shliefer")
    # Print the headings in order
    for line in md.split('\n'):
        if line.startswith('## '):
            print(line)

asyncio.run(main())
