"""
Resume parser: extract and structure text from PDF and DOCX resumes.
- Improves raw text extraction (layout-aware PDF, consistent cleaning).
- Uses regex to detect section headers and split content.
- Optional OCR fallback for scanned/image PDFs (pymupdf + pytesseract).
- Optionally uses AI to refine sections/subsections (see ai_service.parse_resume_sections_with_ai).
"""
import io
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from fastapi import UploadFile
from pypdf import PdfReader

# Optional OCR (scanned PDFs / text in images): pymupdf renders pages, pytesseract extracts text
_OCR_AVAILABLE = False
try:
    import fitz  # pymupdf
    import pytesseract
    from PIL import Image
    _OCR_AVAILABLE = True
except ImportError:
    fitz = None
    pytesseract = None

# ---------------------------------------------------------------------------
# Section detection: canonical names and regex patterns (from config)
# ---------------------------------------------------------------------------

from app.config.section_patterns import (
    CANONICAL_SECTION_ORDER,
    build_section_patterns,
)

# Compiled patterns (loaded from app.config.section_patterns at import).
RESUME_SECTION_PATTERNS: List[Tuple[str, re.Pattern]] = build_section_patterns()

# Max length for a line to be considered a section header (avoids "I have 10 years Experience in..." matching)
SECTION_HEADER_MAX_LEN = 80


def _is_section_header(line: str) -> Optional[str]:
    """If line looks like a section header, return canonical name; else None."""
    stripped = line.strip()
    if len(stripped) > SECTION_HEADER_MAX_LEN:
        return None
    for canonical, pattern in RESUME_SECTION_PATTERNS:
        if pattern.match(stripped):
            return canonical
    return None


# ---------------------------------------------------------------------------
# Text cleaning (shared for PDF and DOCX)
# ---------------------------------------------------------------------------

def _normalize_spaces(text: str) -> str:
    """Replace tabs with space, collapse multiple spaces to one."""
    text = text.replace("\t", " ")
    return re.sub(r" +", " ", text)


def clean_resume_text(text: str) -> str:
    """
    Clean extracted resume text: join mid-sentence line breaks, normalize spaces,
    preserve paragraph breaks and bullet/list starts.
    """
    if not (text or text.strip()):
        return ""
    text = _normalize_spaces(text)
    lines = text.split("\n")
    result: List[str] = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            # Preserve paragraph break (double newline)
            if result and result[-1] != "\n":
                result.append("\n\n")
            else:
                result.append("\n")
            continue

        # Section header: keep as its own line (don't join with previous)
        if _is_section_header(line_stripped):
            if result and result[-1] != "\n":
                result.append("\n")
            result.append(line_stripped)
            continue

        is_bullet_or_list = (
            line_stripped.startswith("-")
            or line_stripped.startswith("*")
            or line_stripped.startswith("•")
            or re.match(r"^\d+[.)]\s", line_stripped)
        )
        prev = result[-1] if result else ""
        prev_ends_colon = prev.rstrip().endswith(":")
        # Don't join content onto a line that is only a section header
        prev_is_header = _is_section_header(prev) is not None

        if result and result[-1] != "\n":
            if is_bullet_or_list or prev_ends_colon or prev_is_header:
                result.append("\n")
                result.append(line_stripped)
            else:
                # Join continuation of same paragraph
                result.append(" ")
                result.append(line_stripped)
        else:
            result.append(line_stripped)

    out = "".join(result)
    out = _normalize_spaces(out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# Alias for backward compatibility
def clean_pdf_text(text: str) -> str:
    return clean_resume_text(text)


# ---------------------------------------------------------------------------
# Section extraction (regex-based)
# ---------------------------------------------------------------------------

def extract_sections_by_regex(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Split cleaned resume text into preamble and named sections using regex.
    Returns (preamble, sections dict). Section names are canonical (summary, experience, etc.).
    """
    if not text or not text.strip():
        return "", {}

    lines = text.split("\n")
    preamble_parts: List[str] = []
    sections: Dict[str, str] = {}
    current_section: Optional[str] = None
    current_content: List[str] = []

    def flush_current():
        if current_section is not None and current_content:
            existing = sections.get(current_section, "")
            sections[current_section] = (existing + "\n" + "\n".join(current_content)).strip() if existing else "\n".join(current_content).strip()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Preserve blank lines: in preamble keep paragraph breaks; in section keep in content
            if current_section is None:
                preamble_parts.append("")
            else:
                current_content.append("")
            continue

        header = _is_section_header(stripped)
        if header is not None:
            flush_current()
            current_section = header
            current_content = []
            continue

        if current_section is None:
            preamble_parts.append(stripped)
        else:
            current_content.append(stripped)

    flush_current()

    preamble = "\n".join(preamble_parts).strip()
    return preamble, sections


def build_full_text(preamble: str, sections: Dict[str, str], use_markdown_headers: bool = True) -> str:
    """
    Rebuild a single resume string from preamble and sections in canonical order.
    If use_markdown_headers is True, prepend "## Section Name" before each section for clarity.
    """
    parts: List[str] = []
    if preamble:
        parts.append(preamble)

    seen = set()
    for canonical in CANONICAL_SECTION_ORDER:
        if canonical == "preamble":
            continue
        content = sections.get(canonical, "").strip()
        if not content:
            continue
        seen.add(canonical)
        if use_markdown_headers:
            title = canonical.replace("_", " ").title()
            parts.append(f"\n\n## {title}\n\n{content}")
        else:
            parts.append("\n\n" + content)

    # Any section not in canonical order (e.g. custom headers we didn't map)
    for name, content in sections.items():
        if name in seen or not content.strip():
            continue
        seen.add(name)
        if use_markdown_headers:
            title = name.replace("_", " ").title()
            parts.append(f"\n\n## {title}\n\n{content.strip()}")
        else:
            parts.append("\n\n" + content.strip())

    return "\n".join(parts).strip() if parts else ""


# ---------------------------------------------------------------------------
# Pipeline config (Phase 2: modular pipeline)
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """
    Configuration for the resume parse pipeline.
    - extractors: mime_type -> (content: bytes) -> raw text
    - cleaner: raw text -> cleaned text
    - section_extractor: cleaned text -> (preamble, sections)
    - canonical_section_order: used by build_full_text (optional override)
    """
    extractors: Dict[str, Callable[[bytes], str]]
    cleaner: Callable[[str], str]
    section_extractor: Callable[[str], Tuple[str, Dict[str, str]]]
    canonical_section_order: List[str]


# ---------------------------------------------------------------------------
# Contact extraction (phone, email, location, LinkedIn, portfolio)
# ---------------------------------------------------------------------------

# Regex for contact info (scan full text so we don't miss sidebar/footer content).
# Allow flexible separators (multiple spaces, en-dash) and 10-digit US numbers.
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]*)?\(?\d{3}\)?[-.\s\u2013]*\d{3}[-.\s\u2013]*\d{4}\b|"
    r"\b\d{3}[-.\s\u2013]+\d{3}[-.\s\u2013]+\d{4}\b|"
    r"\b\d{10}\b|"
    r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b",
    re.UNICODE,
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# URLs: LinkedIn, portfolio, personal site
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-./]+", re.I)
_PORTFOLIO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9.]*\.(?:com|io|co|net|me|dev)(?:/[\w\-./?=&#]*)?",
    re.I,
)
_URL_RE = re.compile(r"https?://[^\s<>\"'\s)]+|(?:www\.)[^\s<>\"'\s)]+")
# Location: "City, ST" or "City, State" or "City | Country" (prefer first ~1200 chars)
_LOCATION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
)


@dataclass
class ExtractedContact:
    """Contact info extracted from resume text."""
    phones: List[str]
    emails: List[str]
    linkedin_urls: List[str]
    portfolio_urls: List[str]
    other_urls: List[str]
    location: Optional[str]


# Contact info is usually in the first N chars (header); scan full text for phone/email/LinkedIn.
_CONTACT_HEADER_CHARS = 2500

# Date-range patterns that must not be treated as phone numbers (e.g. "July 2024 - Present")
_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
)
_PRESENT_RE = re.compile(r"\bpresent\b", re.I)


def _looks_like_date_range(s: str) -> bool:
    """Return True if string looks like a date range (e.g. 'July 2024 - Present'), not a phone."""
    if not s or len(s) > 50:
        return True
    lower = s.lower().strip()
    if _PRESENT_RE.search(lower):
        return True
    if any(m in lower for m in _MONTH_NAMES):
        return True
    # "2024 - 2025" or "2024 – 2025" (en-dash)
    if re.search(r"\d{4}\s*[-–]\s*(?:\d{4}|\w+)", lower):
        return True
    return False


def _is_plausible_phone(s: str) -> bool:
    """Return True if string looks like a real phone number (enough digits, not a date)."""
    if not s or _looks_like_date_range(s):
        return False
    digit_count = sum(c.isdigit() for c in s)
    return digit_count >= 7 and digit_count <= 15


def is_plausible_phone(s: str) -> bool:
    """Public helper: True if string looks like a phone number (not a date range)."""
    return _is_plausible_phone(s)


def extract_contact_from_text(text: str) -> ExtractedContact:
    """
    Scan full resume text for phone, email, location, LinkedIn, and portfolio/website URLs.
    Phone/email/LinkedIn are taken from full text; location and portfolio/other URLs from header zone.
    """
    if not text or not text.strip():
        return ExtractedContact(phones=[], emails=[], linkedin_urls=[], portfolio_urls=[], other_urls=[], location=None)
    raw_phones = _PHONE_RE.findall(text)
    # Drop 10-digit-only matches that look like years (19xx, 20xx) or invalid US area codes.
    # Also drop any match that looks like a date range (e.g. from OCR/layout noise).
    phones = []
    for p in dict.fromkeys(raw_phones):
        p = p.strip()
        if not _is_plausible_phone(p):
            continue
        if len(p) == 10 and p.isdigit():
            if p.startswith(("19", "20")) or p[0] in "01":
                continue  # likely year or invalid area code
        phones.append(p)
    emails = list(dict.fromkeys(_EMAIL_RE.findall(text)))
    linkedin_urls = list(dict.fromkeys(_LINKEDIN_RE.findall(text)))
    linkedin_urls = [u if u.startswith("http") else "https://www." + u.lstrip("./") for u in linkedin_urls]
    header = text[:_CONTACT_HEADER_CHARS]
    portfolio_urls = list(dict.fromkeys(_PORTFOLIO_RE.findall(header)))
    portfolio_urls = [u if u.startswith("http") else "https://" + u for u in portfolio_urls if "linkedin" not in u.lower()]
    other_urls = list(dict.fromkeys(_URL_RE.findall(header)))
    other_urls = [u for u in other_urls if not any(x in u.lower() for x in ["linkedin", "facebook", "twitter"])]
    # Location: take first plausible "City, ST" or "City, State" in first 1200 chars
    head = text[:1200]
    loc_match = _LOCATION_RE.search(head)
    location = None
    if loc_match:
        location = f"{loc_match.group(1)}, {loc_match.group(2)}"
    return ExtractedContact(
        phones=phones,
        emails=emails,
        linkedin_urls=linkedin_urls,
        portfolio_urls=portfolio_urls,
        other_urls=other_urls[:3],
        location=location,
    )


def _format_contact_line(contact: ExtractedContact) -> str:
    """Build a single contact line: location · phone · email · LinkedIn · portfolio."""
    parts = []
    if contact.location:
        parts.append(contact.location)
    for p in contact.phones:
        parts.append(p.strip())
    for e in contact.emails:
        parts.append(e.strip())
    for u in contact.linkedin_urls:
        parts.append(u.strip())
    for u in contact.portfolio_urls:
        parts.append(u.strip())
    for u in contact.other_urls:
        parts.append(u.strip())
    return " · ".join(parts) if parts else ""


def _merge_contact_into_preamble(preamble: str, contact: ExtractedContact) -> str:
    """
    If we extracted contact info that isn't already in the preamble, append a contact line.
    Builds the appended line from only the items missing from preamble to avoid duplication.
    """
    preamble_lower = (preamble or "").lower()

    def already_in_preamble(value: str) -> bool:
        v = value.lower().strip()
        if v in preamble_lower:
            return True
        v_noproto = v.replace("https://", "").replace("http://", "").replace("www.", "")
        return v_noproto in preamble_lower

    added_phones = [p for p in contact.phones if not already_in_preamble(p)]
    added_emails = [e for e in contact.emails if not already_in_preamble(e)]
    added_location = contact.location if (contact.location and not already_in_preamble(contact.location)) else None
    added_linkedin = [u for u in contact.linkedin_urls if not already_in_preamble(u)]
    added_portfolio = [u for u in contact.portfolio_urls if not already_in_preamble(u)]
    added_other = [u for u in contact.other_urls if not already_in_preamble(u)]

    if not (added_phones or added_emails or added_location or added_linkedin or added_portfolio or added_other):
        return preamble

    parts = []
    if added_location:
        parts.append(added_location)
    parts.extend(added_phones)
    parts.extend(added_emails)
    parts.extend(added_linkedin)
    parts.extend(added_portfolio)
    parts.extend(added_other)
    extra_line = " · ".join(parts)
    return (preamble.strip() + "\n\n" + extra_line).strip() if preamble.strip() else extra_line


# ---------------------------------------------------------------------------
# Parsed result (optional structured output)
# ---------------------------------------------------------------------------

@dataclass
class ParsedResume:
    """Structured result of parsing a resume (for future use)."""
    full_text: str
    preamble: str
    sections: Dict[str, str]


def parse_resume_text_to_structure(raw_text: str) -> ParsedResume:
    """
    Clean raw text, extract sections by regex, and return ParsedResume.
    Contact info (phone, email, location, LinkedIn, portfolio) is extracted from the
    full text and merged into the preamble so it is not lost.
    """
    cleaned = clean_resume_text(raw_text)
    preamble, sections = extract_sections_by_regex(cleaned)
    if not sections and cleaned:
        preamble = cleaned
    contact = extract_contact_from_text(cleaned)
    preamble = _merge_contact_into_preamble(preamble or "", contact)
    full_text = build_full_text(preamble, sections)
    return ParsedResume(full_text=full_text, preamble=preamble, sections=sections)


# Default threshold: use AI when preamble is more than this fraction of total content length
PREAMBLE_RATIO_THRESHOLD_FOR_AI = 0.45


def should_use_ai_sections(parsed: ParsedResume) -> bool:
    """
    Return True when AI-based section extraction is likely to improve results.
    Use AI when regex section detection is weak:
    - No sections detected (all content landed in preamble).
    - Only one section (poor split, likely missed headers).
    - Preamble is disproportionately large (> PREAMBLE_RATIO_THRESHOLD_FOR_AI of content),
      suggesting content was misattributed to preamble.
    """
    if not parsed.full_text or not parsed.full_text.strip():
        return False
    total_len = len(parsed.full_text)
    preamble_len = len(parsed.preamble or "")
    section_count = len(parsed.sections)

    if section_count == 0:
        return True
    if section_count == 1:
        return True
    if total_len > 0 and (preamble_len / total_len) > PREAMBLE_RATIO_THRESHOLD_FOR_AI:
        return True
    return False


# ---------------------------------------------------------------------------
# Section validation
# ---------------------------------------------------------------------------

# Validation tiers (Phase 3): at least one of REQUIRED_SECTIONS must be present for valid resume.
REQUIRED_SECTIONS = ("experience", "education")  # at least one required (student may have only education, etc.)
# Common sections; missing is informational only (warnings, not invalid).
COMMON_SECTIONS = ("skills",)
# Optional sections; missing is informational only.
OPTIONAL_SECTIONS = ("summary", "publications", "certifications", "projects", "awards", "other")

# Backward compatibility: "expected" = required + common for warnings
EXPECTED_SECTIONS = REQUIRED_SECTIONS + COMMON_SECTIONS


@dataclass
class ResumeSectionValidation:
    """Result of validating which resume sections were detected."""
    sections_found: List[str]
    sections_missing: List[str]
    optional_missing: List[str]
    has_preamble: bool
    is_valid: bool
    warnings: List[str]


def validate_resume_sections(parsed: ParsedResume) -> ResumeSectionValidation:
    """
    Check which required/optional sections are present in the parsed resume.
    Valid = has preamble and at least one of REQUIRED_SECTIONS (experience or education).
    COMMON_SECTIONS (e.g. skills) and OPTIONAL_SECTIONS missing only produce warnings.
    """
    sections_found: List[str] = []
    sections_missing: List[str] = []
    optional_missing: List[str] = []
    warnings: List[str] = []

    for name, content in (parsed.sections or {}).items():
        if content and str(content).strip():
            sections_found.append(name)

    # Required: at least one of (experience, education) must be present
    required_missing = [n for n in REQUIRED_SECTIONS if n not in sections_found]
    # Sections missing from required + common (for backward-compat warnings)
    for name in EXPECTED_SECTIONS:
        if name not in sections_found:
            sections_missing.append(name)

    for name in OPTIONAL_SECTIONS:
        if name not in sections_found:
            optional_missing.append(name)

    has_preamble = bool(parsed.preamble and str(parsed.preamble).strip())

    if not has_preamble:
        warnings.append("No preamble (name/contact) detected at the top of the resume.")

    for name in sections_missing:
        warnings.append(f"Expected section not found: {name.replace('_', ' ').title()}.")

    # Valid: has preamble and at least one required section (experience or education)
    is_valid = len(required_missing) < len(REQUIRED_SECTIONS) and has_preamble

    return ResumeSectionValidation(
        sections_found=sections_found,
        sections_missing=sections_missing,
        optional_missing=optional_missing,
        has_preamble=has_preamble,
        is_valid=is_valid,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

# Min chars from pypdf below which we use full-document OCR. Also trigger OCR for first page if it's empty.
MIN_EXTRACTED_CHARS_FOR_SKIP_OCR = 80
OCR_DPI = 200  # Higher DPI improves accuracy for small text (e.g. names in headers)
OCR_FIRST_N_PAGES = 2  # Run OCR on the first N pages to catch names/headers in images
# Separator between PDF pages (preserved through clean/section so downstream can detect page boundaries).
PDF_PAGE_SEPARATOR = "\n\n"


def _extract_pdf_text_from_reader(reader: PdfReader) -> Tuple[str, List[str]]:
    """Extract text from all pages; prefer layout mode. Returns (full_text, list of per-page text)."""
    text_parts: List[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text(extraction_mode="layout")
        except (TypeError, ValueError, KeyError):
            t = page.extract_text()
        text_parts.append((t or "").strip())
    full = PDF_PAGE_SEPARATOR.join(text_parts)
    return full, text_parts


def _looks_like_name_or_header(line: str) -> bool:
    """Heuristic: does this line look like a name or header (capitalized, short, name-like patterns)?"""
    if not line or len(line) > 100:
        return False
    stripped = line.strip()
    words = stripped.split()
    if len(words) == 0:
        return False
    if not words[0] or not words[0][0].isupper():
        return False
    # Single capitalized word (e.g. "Gabby" from OCR) - accept if short and letter-only
    if len(words) == 1 and words[0].isalpha() and 2 <= len(words[0]) <= 30:
        return True
    # Common name patterns: "First Last", "First M. Last", "First Last | Email"
    if 2 <= len(words) <= 6:
        capitalized_count = sum(1 for w in words if w and w[0].isupper())
        if capitalized_count >= len(words) * 0.6:
            return True
    return False


def _ocr_pdf_bytes(content: bytes, dpi: int = OCR_DPI) -> str:
    """
    Run OCR on the PDF using PyMuPDF (render pages to images) and Tesseract.
    Returns extracted text or empty string if OCR is unavailable or fails.
    """
    if not _OCR_AVAILABLE or not content or len(content) < 100:
        return ""
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        parts: List[str] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img)
            if text and text.strip():
                parts.append(text.strip())
        doc.close()
        return "\n\n".join(parts) if parts else ""
    except Exception:
        return ""


def _ocr_first_n_pages(content: bytes, n: int) -> List[str]:
    """Run OCR on the first n pages; return list of page texts (empty string for missing/failed pages)."""
    if not _OCR_AVAILABLE or not content or n < 1:
        return []
    result: List[str] = []
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        for i in range(min(n, len(doc))):
            page = doc[i]
            pix = page.get_pixmap(dpi=OCR_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = (pytesseract.image_to_string(img) or "").strip()
            result.append(text)
        doc.close()
    except Exception:
        pass
    return result


def _merge_ocr_into_page(ocr_text: str, pypdf_page: str) -> str:
    """
    If OCR found name-like or extra content not in pypdf, merge it into the page text.
    Returns merged string for that page.
    """
    pypdf_stripped = (pypdf_page or "").strip()
    if not ocr_text:
        return pypdf_stripped
    if len(pypdf_stripped) < 30:
        return ocr_text
    ocr_lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
    pypdf_lines = [line.strip() for line in pypdf_stripped.split("\n") if line.strip()]
    ocr_top_content = []
    for line in ocr_lines[:8]:
        if line in pypdf_lines or any(line.lower() in p.lower() for p in pypdf_lines):
            continue
        if (
            _looks_like_name_or_header(line)
        ):
            ocr_top_content.append(line)
        elif (
            len(line) < 80
            and any(c.isupper() for c in line[:20])
        ):
            ocr_top_content.append(line)
        elif (
            len(line) < 200
            and (_PHONE_RE.search(line) or _EMAIL_RE.search(line))
        ):
            # Include lines that look like contact info (phone/email) so they are in merged text for extraction
            ocr_top_content.append(line)
    if ocr_top_content:
        return "\n".join(ocr_top_content) + "\n\n" + pypdf_stripped
    if len(ocr_text) > len(pypdf_stripped) * 1.5:
        return ocr_text
    return pypdf_stripped


def _extract_pdf_text_with_ocr_fallback(content: bytes) -> str:
    """
    Extract text from PDF: use pypdf first; fall back to OCR when extraction is
    poor (e.g. scanned PDF or text in images like candidate name).
    Runs OCR on the first OCR_FIRST_N_PAGES pages to catch names/headers in images.
    """
    pdf_file = io.BytesIO(content)
    reader = PdfReader(pdf_file)
    full_pypdf, per_page = _extract_pdf_text_from_reader(reader)
    total_len = len(full_pypdf.strip())

    # If very little text extracted, use full-document OCR
    if total_len < MIN_EXTRACTED_CHARS_FOR_SKIP_OCR and _OCR_AVAILABLE:
        ocr_text = _ocr_pdf_bytes(content)
        if ocr_text and len(ocr_text.strip()) > total_len:
            return ocr_text

    # Run OCR on first N pages and merge with pypdf
    if _OCR_AVAILABLE and per_page:
        n_ocr = min(OCR_FIRST_N_PAGES, len(per_page))
        if n_ocr > 0:
            try:
                ocr_pages = _ocr_first_n_pages(content, n_ocr)
                if ocr_pages:
                    merged: List[str] = []
                    for i in range(n_ocr):
                        pypdf_page = (per_page[i] or "").strip()
                        ocr_page_text = ocr_pages[i] if i < len(ocr_pages) else ""
                        merged.append(_merge_ocr_into_page(ocr_page_text, pypdf_page))
                    rest = "\n".join(per_page[n_ocr:]).strip()
                    return "\n\n".join(filter(None, merged + [rest])) if rest else "\n\n".join(filter(None, merged))
            except Exception:
                pass

    return full_pypdf


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------

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
        elif child.tag.endswith("sdt"):
            sdt_content = child.find(child.tag.replace("sdt", "sdtContent"))
            if sdt_content is not None:
                for sdt_child in sdt_content.iterchildren():
                    if isinstance(sdt_child, CT_P):
                        yield Paragraph(sdt_child, parent)
                    elif isinstance(sdt_child, CT_Tbl):
                        yield Table(sdt_child, parent)


def get_text_recursive(element):
    text = []
    if isinstance(element, Paragraph):
        if element.text.strip():
            text.append(element.text)
        try:
            for txbx in element._p.xpath(".//w:txbxContent"):
                for child in txbx.iterchildren():
                    if child.tag.endswith("p"):
                        p_text = "".join(
                            (node.text or "") for node in child.iterdescendants() if node.tag.endswith("t")
                        )
                        if p_text.strip():
                            text.append(p_text)
                    elif child.tag.endswith("tbl"):
                        for row in child.xpath(".//w:tr"):
                            row_text = []
                            for cell in row.xpath(".//w:tc"):
                                cell_text = []
                                for p in cell.xpath(".//w:p"):
                                    p_text = "".join((n.text or "") for n in p.iterdescendants() if n.tag.endswith("t"))
                                    if p_text.strip():
                                        cell_text.append(p_text)
                                if cell_text:
                                    row_text.append(" ".join(cell_text))
                            if row_text:
                                text.append(" | ".join(row_text))
        except Exception:
            pass
    elif hasattr(element, "paragraphs") or hasattr(element, "rows") or isinstance(element, (_Document, _Cell)):
        for block in iter_block_items(element):
            if isinstance(block, Paragraph):
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
    return "\n".join(t for t in text if t)


# ---------------------------------------------------------------------------
# Pipeline: extractor implementations and run_pipeline
# ---------------------------------------------------------------------------

def _extract_raw_pdf(content: bytes) -> str:
    """Extract raw text from PDF bytes (layout + OCR fallback)."""
    return _extract_pdf_text_with_ocr_fallback(content)


def _extract_raw_docx(content: bytes) -> str:
    """Extract raw text from DOCX bytes (body, tables, text boxes)."""
    doc = Document(io.BytesIO(content))
    return get_text_recursive(doc)


def _extract_raw_plain(content: bytes) -> str:
    """Decode bytes as UTF-8 (fallback for unknown or text/plain)."""
    return content.decode("utf-8", errors="replace")


# Default pipeline: PDF, DOCX, plain text extractors; shared cleaner and regex sections.
DEFAULT_PIPELINE_CONFIG = PipelineConfig(
    extractors={
        "application/pdf": _extract_raw_pdf,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _extract_raw_docx,
        "text/plain": _extract_raw_plain,
    },
    cleaner=clean_resume_text,
    section_extractor=extract_sections_by_regex,
    canonical_section_order=CANONICAL_SECTION_ORDER,
)


def run_pipeline(content: bytes, mime_type: str, config: Optional[PipelineConfig] = None) -> ParsedResume:
    """
    Run the parse pipeline: extract -> clean -> sections -> contact merge -> build.
    Uses config.extractors[mime_type] or falls back to text/plain decode.
    """
    cfg = config or DEFAULT_PIPELINE_CONFIG
    extract = cfg.extractors.get(mime_type) or cfg.extractors.get("text/plain")
    if extract is not None:
        raw = extract(content)
    else:
        raw = _extract_raw_plain(content)

    cleaned = cfg.cleaner(raw)
    preamble, sections = cfg.section_extractor(cleaned)
    if not sections and cleaned:
        preamble = cleaned
    contact = extract_contact_from_text(cleaned)
    preamble = _merge_contact_into_preamble(preamble or "", contact)
    full_text = build_full_text(preamble, sections)
    return ParsedResume(full_text=full_text, preamble=preamble, sections=sections)


async def parse_pdf(file: UploadFile) -> ParsedResume:
    """Extract and clean text from a PDF resume; return structured ParsedResume (use .full_text for string)."""
    content = await file.read()
    return run_pipeline(content, "application/pdf", DEFAULT_PIPELINE_CONFIG)


async def parse_docx(file: UploadFile) -> ParsedResume:
    """Extract and clean text from a DOCX resume; return structured ParsedResume (use .full_text for string)."""
    content = await file.read()
    return run_pipeline(
        content,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DEFAULT_PIPELINE_CONFIG,
    )


# ---------------------------------------------------------------------------
# Job description scraping
# ---------------------------------------------------------------------------

def scrape_url(url: str) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        return text[:10000]
    except Exception as e:
        print(f"Error scraping URL: {e}")
        return ""
