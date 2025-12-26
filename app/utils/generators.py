from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from io import BytesIO
import re

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
        elif '|' in line and not line.startswith('-') and not line.startswith('*'):
            # Handle Date Alignment (Role | Date)
            parts = line.split('|')
            if len(parts) == 2:
                table = doc.add_table(rows=1, cols=2)
                table.autofit = False
                table.allow_autofit = False
                
                # Set column widths (approximate)
                # Word table column widths are tricky, but this helps
                for cell in table.columns[0].cells:
                    cell.width = Inches(4.5)
                for cell in table.columns[1].cells:
                    cell.width = Inches(2.0)

                # Left Cell (Role)
                left_cell = table.cell(0, 0)
                left_p = left_cell.paragraphs[0]
                left_part = parts[0].strip()
                
                # Handle bold in left cell
                if '**' in left_part:
                    left_p.clear()
                    sub_parts = re.split(r'(\*\*.*?\*\*)', left_part)
                    for part in sub_parts:
                        if part.startswith('**') and part.endswith('**'):
                            run = left_p.add_run(part[2:-2])
                            run.bold = True
                        else:
                            left_p.add_run(part)
                else:
                    left_p.text = left_part

                # Right Cell (Date)
                right_cell = table.cell(0, 1)
                right_p = right_cell.paragraphs[0]
                right_p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                right_part = parts[1].strip()
                
                # Handle bold in right cell
                if '**' in right_part:
                    right_p.clear()
                    sub_parts = re.split(r'(\*\*.*?\*\*)', right_part)
                    for part in sub_parts:
                        if part.startswith('**') and part.endswith('**'):
                            run = right_p.add_run(part[2:-2])
                            run.bold = True
                        else:
                            right_p.add_run(part)
                else:
                    right_p.text = right_part
            else:
                # Fallback if split fails
                p = doc.add_paragraph(line)
        elif line.startswith('- ') or line.startswith('* '):
            # Bullet point
            p = doc.add_paragraph(line[2:], style='List Bullet')
            p.paragraph_format.space_after = Pt(2)
            
            # Handle bold in bullets
            if '**' in line:
                p.clear()
                # Re-add bullet content
                content_text = line[2:]
                parts = re.split(r'(\*\*.*?\*\*)', content_text)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        run = p.add_run(part[2:-2])
                        run.bold = True
                    else:
                        p.add_run(part)
        else:
            # Normal text
            p = doc.add_paragraph(line)
            p.paragraph_format.space_after = Pt(6)
            
            # Handle bold text (simple implementation for **bold**)
            if '**' in line:
                # Clear the run created by add_paragraph and rebuild it
                p.clear()
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        run = p.add_run(part[2:-2])
                        run.bold = True
                    else:
                        p.add_run(part)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream
