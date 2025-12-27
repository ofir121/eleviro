from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.shared import OxmlElement
from docx.oxml.ns import qn
from io import BytesIO
import re

def add_hyperlink(paragraph, text, url, is_bold=False):
    """
    Add a hyperlink to a paragraph.
    """
    # This gets access to the document.xml.rels file and gets a new relation id value
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    # Create the w:hyperlink tag and add needed values
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    # Create a w:r element and a new w:rPr element
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    
    # Add color (Blue)
    color = OxmlElement('w:color')
    color.set(qn('w:val'), "0000FF")
    rPr.append(color)
    
    # Add underline
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rPr.append(u)
    
    if is_bold:
        b = OxmlElement('w:b')
        rPr.append(b)

    new_run.append(rPr)
    
    # Add text
    t = OxmlElement('w:t')
    t.text = text
    new_run.append(t)
    
    hyperlink.append(new_run)

    # Append hyperlink to the paragraph element
    paragraph._p.append(hyperlink)

    return hyperlink

def process_text(paragraph, text, default_bold=False, default_color=None):
    """
    Process text for bold markers (**text**) and markdown links ([text](url)).
    """
    # Regex to find **bold** OR [link](url)
    # This regex captures delimiters to keep them in the split list
    pattern = r'(\*\*.*?\*\*|\[.*?\]\(.*?\))'
    parts = re.split(pattern, text)
    
    for part in parts:
        if not part:
            continue
            
        if part.startswith('**') and part.endswith('**'):
            # Bold text
            content = part[2:-2]
            # Check if there is a link inside the bold text
            link_match = re.match(r'\[(.*?)\]\((.*?)\)', content)
            if link_match:
                # Link inside bold
                link_text = link_match.group(1)
                link_url = link_match.group(2)
                add_hyperlink(paragraph, link_text, link_url, is_bold=True)
            else:
                run = paragraph.add_run(content)
                run.bold = True
                if default_color:
                    run.font.color.rgb = default_color
                    
        elif part.startswith('[') and part.endswith(')') and '](' in part:
            # Link
            link_match = re.match(r'\[(.*?)\]\((.*?)\)', part)
            if link_match:
                link_text = link_match.group(1)
                link_url = link_match.group(2)
                add_hyperlink(paragraph, link_text, link_url, is_bold=default_bold)
            else:
                # Fallback
                run = paragraph.add_run(part)
                if default_bold: run.bold = True
                if default_color: run.font.color.rgb = default_color
        else:
            # Normal text
            run = paragraph.add_run(part)
            if default_bold: run.bold = True
            if default_color: run.font.color.rgb = default_color

def create_docx(content: str) -> BytesIO:
    doc = Document()
    
    # Set narrow margins for compact look
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Simple Markdown Parser
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('# '):
            # Heading 1
            p = doc.add_heading(line[2:], level=1)
            p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        elif line.startswith('## '):
            # Heading 2
            p = doc.add_heading(line[3:], level=2)
            p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        elif line.startswith('### '):
            # Heading 3
            p = doc.add_heading(line[4:], level=3)
            p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        elif '|' in line and not line.startswith('- ') and not line.startswith('* '):
            # Handle Date Alignment (Role | Date)
            parts = line.split('|')
            # Check if it's a valid Role/Education line (shouldn't be too long, e.g. > 120 chars)
            if len(parts) == 2 and len(parts[0].strip()) < 120:
                table = doc.add_table(rows=1, cols=2)
                table.autofit = False
                table.allow_autofit = False
                
                # Set column widths (3/4 and 1/4 split)
                for cell in table.columns[0].cells:
                    cell.width = Inches(5.25) # 75%
                for cell in table.columns[1].cells:
                    cell.width = Inches(1.75) # 25%
                
                # Prevent table from being split across pages
                tbl = table._tbl
                tblPr = tbl.tblPr if tbl.tblPr is not None else tbl._add_tblPr()
                from docx.oxml import OxmlElement
                cantSplit = OxmlElement('w:cantSplit')
                for tr in tbl.tr_lst:
                    trPr = tr.get_or_add_trPr()
                    trPr.append(cantSplit)

                # Left Cell (Role)
                left_cell = table.cell(0, 0)
                left_p = left_cell.paragraphs[0]
                left_part = parts[0].strip()
                
                # Handle bold in left cell and make it BLUE
                # Clear default paragraph content
                left_p.clear()
                process_text(left_p, left_part, default_color=RGBColor(115, 147, 179))

                # Right Cell (Date)
                right_cell = table.cell(0, 1)
                right_p = right_cell.paragraphs[0]
                right_p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                right_part = parts[1].strip()
                
                # Handle bold in right cell
                right_p.clear()
                process_text(right_p, right_part)

            else:
                # Fallback if split fails
                p = doc.add_paragraph()
                process_text(p, line)
        elif line.startswith('- ') or line.startswith('* '):
            # Bullet point
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after = Pt(2)
            process_text(p, line[2:])
        else:
            # Normal text
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            process_text(p, line)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream
