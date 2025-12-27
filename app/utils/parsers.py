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
    links = []
    
    for page in reader.pages:
        text += page.extract_text() + "\n"
        
        # Extract links
        if "/Annots" in page:
            for annot in page["/Annots"]:
                obj = annot.get_object()
                if "/A" in obj and "/URI" in obj["/A"]:
                    uri = obj["/A"]["/URI"]
                    links.append(uri)
    
    if links:
        text += "\n\n## Extracted Links\n"
        for link in set(links): # Deduplicate
            text += f"- {link}\n"
            
    return text

from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        return

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)
        elif child.tag.endswith('sdt'):
            # Structured Document Tag
            # Content is in sdtContent
            sdt_content = child.find(child.tag.replace('sdt', 'sdtContent'))
            if sdt_content is not None:
                for sdt_child in sdt_content.iterchildren():
                    if isinstance(sdt_child, CT_P):
                        yield Paragraph(sdt_child, parent)
                    elif isinstance(sdt_child, CT_Tbl):
                        yield Table(sdt_child, parent)
        
    # Also look for text boxes within the parent element's descendants
    # Text boxes are usually in w:drawing -> wp:inline or wp:anchor -> a:graphic -> a:graphicData -> w:txbxContent
    # But simpler to just search for w:txbxContent
    # Note: This might duplicate text if we iterate over everything, but since we are iterating over children of body/cell,
    # text boxes might be nested deep.
    # A better approach for text boxes is to find them specifically if they are not direct children.
    # However, let's try to find all paragraphs, including those in text boxes.
    
    # Alternative strategy: Use XPath to find all paragraphs in the document, including those in text boxes.
    # But we want to preserve order as much as possible.
    # Text boxes are often anchored to a paragraph.
    
    # Let's stick to the current structure but add a check for text boxes in the recursive get_text_recursive.

def get_text_recursive(element):
    text = []
    
    # If element is a Paragraph, it might contain a text box (drawing)
    if isinstance(element, Paragraph):
        if element.text.strip():
            text.append(element.text)
        
        # Check for text boxes anchored to this paragraph
        # This requires digging into the XML of the paragraph
        # w:drawing//w:txbxContent
        if element._p.xpath('.//w:txbxContent'):
            for txbx in element._p.xpath('.//w:txbxContent'):
                # Iterate over children of the text box content (paragraphs and tables)
                for child in txbx.iterchildren():
                    if child.tag.endswith('p'):
                        # Extract text from paragraph
                        p_text = ""
                        for node in child.iterdescendants():
                            if node.tag.endswith('t'):
                                p_text += node.text or ""
                        if p_text.strip():
                            text.append(p_text)
                    elif child.tag.endswith('tbl'):
                        # Extract text from table
                        # This is a bit complex without wrapping in python-docx Table object
                        # But we can iterate rows/cells/paragraphs
                        for row in child.xpath('.//w:tr'):
                            row_text = []
                            for cell in row.xpath('.//w:tc'):
                                cell_text = []
                                for p in cell.xpath('.//w:p'):
                                    p_text = ""
                                    for node in p.iterdescendants():
                                        if node.tag.endswith('t'):
                                            p_text += node.text or ""
                                    if p_text.strip():
                                        cell_text.append(p_text)
                                if cell_text:
                                    row_text.append(" ".join(cell_text))
                            if row_text:
                                text.append(" | ".join(row_text))

    # If element is Document or Cell or Table, iterate block items
    elif hasattr(element, 'paragraphs') or hasattr(element, 'rows') or isinstance(element, _Document) or isinstance(element, _Cell):
         for block in iter_block_items(element):
            if isinstance(block, Paragraph):
                # Recursive call to handle text boxes inside paragraphs
                text.append(get_text_recursive(block))
            elif isinstance(block, Table):
                for row in block.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = get_text_recursive(cell)
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        text.append(" | ".join(row_text))
    
    # Handle Structured Document Tags (SDT)
    # These are not yielded by iter_block_items for Document, but might be present in the XML
    # If we are at the Document level, we might need to look for them explicitly if they are top-level
    # But iter_block_items only iterates P and Tbl.
    # We should update iter_block_items to include SDT content.
    
    return "\n".join([t for t in text if t])

async def parse_docx(file: UploadFile) -> str:
    content = await file.read()
    docx_file = io.BytesIO(content)
    doc = Document(docx_file)
    return get_text_recursive(doc)

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
