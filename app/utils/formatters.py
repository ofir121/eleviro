import re
from typing import Dict, List, Optional
from app.utils.parsers import ParsedResume, ExtractedContact
from app.config.section_patterns import CANONICAL_SECTION_ORDER

def format_contact_info(name: str, contact: ExtractedContact) -> str:
    """
    Format the top header containing Name and Contact Information.
    Name will be H1 (# Name), centered.
    Contact info on the next line separated by middle dots (·).
    """
    parts = []
    
    if contact.location:
        parts.append(contact.location.strip())
    
    # We may have multiple phones, emails, etc. Only use the first one if present to keep it clean,
    # or join them. Let's just use the first of each.
    for p in (contact.phones or [])[:1]:
        parts.append(p.strip())
        
    for e in (contact.emails or [])[:1]:
        parts.append(e.strip())
        
    for u in (contact.linkedin_urls or [])[:1]:
        # Clean up URL for display
        display_url = u.replace("https://", "").replace("http://", "").replace("www.", "")
        parts.append(display_url.strip())
        
    for u in (contact.portfolio_urls or [])[:1]:
        display_url = u.replace("https://", "").replace("http://", "").replace("www.", "")
        parts.append(display_url.strip())
        
    # If no portfolio, maybe fallback to other urls
    if not contact.portfolio_urls and contact.other_urls:
        for u in contact.other_urls[:1]:
            display_url = u.replace("https://", "").replace("http://", "").replace("www.", "")
            parts.append(display_url.strip())

    if contact.security_clearance:
        parts.append(contact.security_clearance.strip())

    contact_line = " · ".join(parts)
    
    # Default name if empty
    display_name = name.strip() if name and name.strip() else "Candidate Name"
    
    header = f"# {display_name}"
    if contact_line:
        header += f"\n{contact_line}"
        
    return header

def format_skills_section(text: str) -> str:
    """
    Format skills into **Category**: Skill 1, Skill 2 format if possible,
    or just ensure they are clean.
    """
    if not text or not text.strip():
        return ""
    
    lines = text.strip().split("\n")
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Remove leading bullets if any
        line = re.sub(r"^[-•]\s+|^\*\s+", "", line)
        
        # Check if it's already a category format: Category: Skill1, Skill2
        if ":" in line:
            parts = line.split(":", 1)
            category = parts[0].strip()
            # Remove bolding if already present
            category = category.replace("**", "")
            # Remove brackets from category if present
            if category.startswith("[") and category.endswith("]"):
                category = category[1:-1].strip()
            
            skills = parts[1].strip()
            
            # Remove brackets if present
            if skills.startswith("[") and skills.endswith("]"):
                skills = skills[1:-1].strip()
            
            formatted_lines.append(f"**{category}**: {skills}")
        else:
            # No category, just list it
            formatted_lines.append(line)
            
    return "\n".join(formatted_lines)

def _is_headline(line: str) -> bool:
    """
    Determine if a line is a headline (e.g. "Role | Date" or "Degree | School").
    Headlines usually don't start with bullet points and often contain a pipe '|'.
    Sometimes they are just short lines with dates.
    """
    line = line.strip()
    # It shouldn't be a bullet point (dash/dot/asterisk followed by space)
    # Note: don't confuse bolding (**text**) with bullet points (* text).
    if line.startswith(("- ", "• ", "* ")) or line == "-" or line == "•" or line == "*":
        return False
        
    # If it has a pipe, it's very likely a headline, provided it isn't absurdly long
    if "|" in line and len(line) < 200:
        return True
        
    # If it has a date-like string (e.g. 2020 - 2022) and is short
    if re.search(r"\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b|\b(19|20)\d{2}\b", line) and len(line) < 120:
        return True
        
    return False

# Matches a line that is ONLY a date range (e.g. "OCT 2018 – OCT 2020", "2020 - PRESENT"),
# with no role/company text alongside it.
_DATE_ONLY_RE = re.compile(
    r"^(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}\s*[-–—]\s*"
    r"(?:PRESENT|CURRENT|(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2})$",
    re.IGNORECASE,
)

def _repair_misplaced_dates(lines: List[str]) -> List[str]:
    """
    Some source documents place the date range on its own line ABOVE the
    role/company/location line (e.g. when the date sat in a separate column
    or cell). This produces entries like:
        OCT 2018 – OCT 2020
        - Data Scientist, Bar-Ilan University Thesis, Ramat Gan, Israel
    instead of the expected "Role, Company, Location DATE" on one line.

    Detect a standalone date-only line immediately followed by a bulleted,
    comma-containing line with no date of its own, and merge them into a
    single proper headline (role line + trailing date), matching the format
    of sibling entries.
    """
    repaired = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if _DATE_ONLY_RE.match(line):
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n:
                next_line = lines[j].strip()
                next_clean = re.sub(r"^[-•]\s+|^\*\s+", "", next_line)
                is_bullet = next_line != next_clean
                if (
                    is_bullet
                    and "," in next_clean
                    and not _DATE_ONLY_RE.search(next_clean)
                    and not re.search(r"\b(19|20)\d{2}\b", next_clean)
                ):
                    repaired.append(f"{next_clean} {line}")
                    i = j + 1
                    continue
        repaired.append(lines[i])
        i += 1
    return repaired

def _clean_headline(line: str) -> str:
    """
    Ensure the headline has the left part bolded if not already.
    E.g. "Software Engineer, Google | 2020 - 2022" -> "**Software Engineer**, Google | 2020 - 2022"
    """
    line = line.strip()
    
    # Remove any stray leading bullets just in case
    line = re.sub(r"^[-•]\s+|^\*\s+", "", line)
    
    if "**" in line:
        return line # Already has some bolding
        
    if "|" in line:
        parts = line.split("|", 1)
        left = parts[0].strip()
        right = parts[1].strip()
        
        # Try to bold just the role/degree (before comma)
        if "," in left:
            left_parts = left.split(",", 1)
            bold_part = left_parts[0].strip()
            rest_part = left_parts[1].strip()
            return f"**{bold_part}**, {rest_part} | {right}"
        else:
            return f"**{left}** | {right}"
            
    return line

def format_experience_section(text: str) -> str:
    """
    Ensure experience entries have properly bolded headers and all details under them are bullet points.
    """
    if not text or not text.strip():
        return ""
        
    lines = text.strip().split("\n")
    lines = _repair_misplaced_dates(lines)
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append("")
            continue

        if _is_headline(line):
            # It's a header line
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.append(_clean_headline(line))
        else:
            # It's a body line, ensure it's a bullet point
            # Remove existing bullets first to normalize
            clean_line = re.sub(r"^[-•]\s+|^\*\s+", "", line)
            formatted_lines.append(f"- {clean_line}")

    # Clean up excessive blank lines
    result = "\n".join(formatted_lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip()

def format_education_section(text: str) -> str:
    """
    Format education/honors/publications/projects entries the same way as experience:
    a bolded headline (Degree/Award, School | Date) followed by bullet-pointed detail lines.
    """
    if not text or not text.strip():
        return ""

    lines = text.strip().split("\n")
    lines = _repair_misplaced_dates(lines)
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if _is_headline(line):
            # It's a header line
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.append(_clean_headline(line))
        else:
            # It's a body line, ensure it's a bullet point
            clean_line = re.sub(r"^[-•]\s+|^\*\s+", "", line)
            formatted_lines.append(f"- {clean_line}")

    result = "\n".join(formatted_lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip()

def format_certifications_section(text: str) -> str:
    """
    Format certifications. One per line, no bullets, styled like a headline.
    """
    if not text or not text.strip():
        return ""
        
    lines = text.strip().split("\n")
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Clean bullets
        line = re.sub(r"^[-•]\s+|^\*\s+", "", line)
        
        # If it doesn't have a pipe, try to add one to align with standard format
        if "|" not in line:
            # Just bold the whole thing and add a pipe at the end if no date found
            if not "**" in line:
                line = f"**{line}** |"
                
        formatted_lines.append(_clean_headline(line))
        
    return "\n".join(formatted_lines)

def build_markdown_resume(parsed_resume: ParsedResume, contact: ExtractedContact, candidate_name: str) -> str:
    """
    Orchestrate the deterministic formatting of the entire resume.
    """
    parts = []
    
    # 1. Contact Info
    header_md = format_contact_info(candidate_name, contact)
    parts.append(header_md)
    
    sections = parsed_resume.sections or {}
    
    # 1.5 Extract hidden summary from preamble
    if parsed_resume.preamble and "summary" not in sections:
        preamble_lines = parsed_resume.preamble.split("\n")
        summary_lines = []
        for i, line in enumerate(preamble_lines):
            line = line.strip()
            if not line: continue
            
            has_contact = bool(re.search(r"[\w\.-]+@[\w\.-]+", line) or re.search(r"\d{3}[-\.\s]\d{3}[-\.\s]\d{4}", line) or "linkedin.com" in line.lower() or "github.com" in line.lower())
            
            # If it's a very long line, it likely contains a summary paragraph
            if len(line) > 150 or (has_contact and len(line) > 100):
                start_idx = 0
                for e in (contact.emails or []):
                    idx = line.find(e)
                    if idx != -1: start_idx = max(start_idx, idx + len(e))
                for p in (contact.phones or []):
                    idx = line.find(p)
                    if idx != -1: start_idx = max(start_idx, idx + len(p))
                for u in (contact.linkedin_urls or []) + (contact.portfolio_urls or []) + (contact.other_urls or []):
                    idx = line.find(u)
                    if idx != -1: start_idx = max(start_idx, idx + len(u))
                    
                clean_summary = line[start_idx:]
                
                # Remove location or name if they appear after the slice
                if candidate_name: clean_summary = clean_summary.replace(candidate_name, "")
                if contact.location: clean_summary = clean_summary.replace(contact.location, "")
                if contact.security_clearance: clean_summary = clean_summary.replace(contact.security_clearance, "")
                
                # Remove stray social-media label words (e.g. "LinkedIn", "GitHub")
                # that may appear as plain text before/after a URL was stripped out.
                clean_summary = re.sub(
                    r"(?i)\b(linkedin|github|twitter|facebook|instagram|portfolio)\b",
                    "",
                    clean_summary,
                )
                
                # Strip leading non-alphanumeric characters (bullets, dots, pipes, spaces)
                clean_summary = re.sub(r"^[^a-zA-Z0-9]+", "", clean_summary.strip())
                if clean_summary:
                    summary_lines.append(clean_summary)
            elif not has_contact and len(line) > 30:
                summary_lines.append(line)
                
        if summary_lines:
            sections["summary"] = "\n".join(summary_lines)

    # Track which sections we've processed to avoid duplicates
    processed_sections = set()
    
    for canonical in CANONICAL_SECTION_ORDER:
        if canonical == "preamble":
            continue
            
        content = sections.get(canonical, "").strip()
        if not content:
            continue
            
        processed_sections.add(canonical)
        
        # Apply specific formatting rules based on section type
        if canonical == "summary":
            # Strip stray social-media label words (e.g. "LinkedIn ·") that may have
            # leaked into the summary from the contact header during parsing.
            content = re.sub(
                r"(?i)\b(linkedin|github|twitter|facebook|instagram|portfolio)\b",
                "",
                content,
            )
            # Clean up any leading separator characters left behind (·, |, -, spaces)
            content = re.sub(r"^[\s·|,\-–—]+", "", content.strip())
            formatted_content = content
        elif canonical == "skills":
            formatted_content = format_skills_section(content)
        elif canonical == "experience":
            formatted_content = format_experience_section(content)
        elif canonical in ("education", "publications", "projects", "awards", "other"):
            formatted_content = format_education_section(content) # Use same logic as education
        elif canonical == "certifications":
            formatted_content = format_certifications_section(content)
        else:
            formatted_content = content
            
        if formatted_content:
            title = canonical.replace("_", " ").title()
            parts.append(f"## {title}\n{formatted_content}")
            
    # Handle any extra sections that weren't in the canonical order
    for name, content in sections.items():
        if name in processed_sections or not content.strip():
            continue
            
        title = name.replace("_", " ").title()
        # Apply general formatting (similar to experience/education to be safe)
        formatted_content = format_education_section(content.strip())
        parts.append(f"## {title}\n{formatted_content}")
        
    final_markdown = "\n\n".join(parts)
    return final_markdown
