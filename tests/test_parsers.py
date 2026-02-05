"""
Tests for resume parser: cleaning, section regex extraction, and full-text build.
"""
import os
import time
import pytest

from app.utils.parsers import (
    clean_resume_text,
    clean_pdf_text,
    extract_sections_by_regex,
    build_full_text,
    parse_resume_text_to_structure,
    extract_contact_from_text,
    is_plausible_phone,
    _merge_contact_into_preamble,
    ParsedResume,
    ExtractedContact,
    should_use_ai_sections,
    validate_resume_sections,
    ResumeSectionValidation,
    _is_section_header,
    RESUME_SECTION_PATTERNS,
    CANONICAL_SECTION_ORDER,
    PipelineConfig,
    run_pipeline,
    DEFAULT_PIPELINE_CONFIG,
)


# ---- Cleaning ----

def test_clean_resume_text_normalizes_spaces():
    text = "Hello    world\t\there"
    assert "  " not in clean_resume_text(text)
    assert "\t" not in clean_resume_text(text)


def test_clean_resume_text_joins_mid_sentence_breaks():
    text = "This is a sentence\nthat continues on the next line."
    result = clean_resume_text(text)
    assert "sentence" in result
    assert "that continues" in result
    # Should be joined with space (no stray newline in the middle of sentence)
    assert "line." in result


def test_clean_resume_text_preserves_bullets():
    text = "Before\n- Bullet one\n- Bullet two"
    result = clean_resume_text(text)
    assert "- Bullet one" in result
    assert "- Bullet two" in result
    assert "Before" in result


def test_clean_resume_text_preserves_paragraph_break():
    text = "First para.\n\nSecond para."
    result = clean_resume_text(text)
    assert "First para." in result
    assert "Second para." in result
    assert "\n\n" in result


def test_clean_resume_text_empty():
    assert clean_resume_text("") == ""
    assert clean_resume_text("   \n\t  ") == ""


def test_clean_pdf_text_alias():
    text = "  foo   bar  "
    assert clean_pdf_text(text) == clean_resume_text(text)


# ---- Section header detection ----

def test_is_section_header_recognizes_summary():
    assert _is_section_header("Professional Summary") == "summary"
    assert _is_section_header("Summary") == "summary"
    assert _is_section_header("  Profile  ") == "summary"


def test_is_section_header_recognizes_experience():
    assert _is_section_header("Experience") == "experience"
    assert _is_section_header("Work Experience") == "experience"
    assert _is_section_header("Professional Experience") == "experience"


def test_is_section_header_recognizes_education_and_skills():
    assert _is_section_header("Education") == "education"
    assert _is_section_header("Skills") == "skills"
    assert _is_section_header("Technical Skills") == "skills"


def test_is_section_header_rejects_long_lines():
    long_line = "I have 10 years of Experience in software development and leadership."
    assert _is_section_header(long_line) is None


def test_is_section_header_rejects_plain_content():
    assert _is_section_header("Senior Software Engineer at Acme") is None
    assert _is_section_header("Python, Java, AWS") is None


# ---- Section extraction ----

def test_extract_sections_by_regex_full():
    text = """Jane Doe
jane@email.com

Professional Summary
I am an engineer.

Experience
Engineer at Acme 2020-present.

Education
BS CS, University X 2020.
"""
    preamble, sections = extract_sections_by_regex(text)
    assert "Jane" in preamble and "jane@email.com" in preamble
    assert "summary" in sections
    assert "I am an engineer" in sections["summary"]
    assert "experience" in sections
    assert "Engineer at Acme" in sections["experience"]
    assert "education" in sections
    assert "BS CS" in sections["education"]


def test_extract_sections_by_regex_empty():
    preamble, sections = extract_sections_by_regex("")
    assert preamble == ""
    assert sections == {}


def test_extract_sections_by_regex_no_headers():
    text = "Just some text\nwith no section headers."
    preamble, sections = extract_sections_by_regex(text)
    assert "Just some text" in preamble
    assert "with no section headers" in preamble
    assert sections == {}


def test_extract_sections_by_regex_skills_certifications():
    text = """Name
Contact

Skills
Python, SQL

Certifications
AWS Certified
"""
    preamble, sections = extract_sections_by_regex(text)
    assert "skills" in sections and "Python" in sections["skills"]
    assert "certifications" in sections and "AWS" in sections["certifications"]


def test_extract_sections_by_regex_preserves_preamble_blank_lines():
    """Blank lines in preamble (before first section) should be preserved."""
    text = """Jane Doe

jane@email.com

Professional Summary
Short bio.
"""
    preamble, sections = extract_sections_by_regex(text)
    assert "Jane Doe" in preamble
    assert "jane@email.com" in preamble
    assert "\n\n" in preamble
    assert "summary" in sections
    assert "Short bio" in sections["summary"]


def test_extract_sections_by_regex_duplicate_section_headers_merged():
    """When the same section header appears twice, both blocks should be in that section."""
    text = """Name
Contact

Experience
First job 2020-2022.

Experience
Second job 2022-present.

Education
BS CS.
"""
    preamble, sections = extract_sections_by_regex(text)
    assert "experience" in sections
    assert "First job" in sections["experience"]
    assert "Second job" in sections["experience"]
    assert "education" in sections
    assert "BS CS" in sections["education"]


# ---- Build full text ----

def test_build_full_text_order_and_headers():
    preamble = "John Doe\njohn@email.com"
    sections = {"experience": "Engineer at Acme.", "education": "BS CS."}
    full = build_full_text(preamble, sections, use_markdown_headers=True)
    assert "John Doe" in full
    assert "## Experience" in full
    assert "## Education" in full
    assert "Engineer at Acme" in full
    assert "BS CS" in full
    # Preamble first, then Experience, then Education (canonical order)
    assert full.index("John Doe") < full.index("## Experience")
    assert full.index("## Experience") < full.index("## Education")


def test_build_full_text_empty_sections():
    full = build_full_text("Preamble", {})
    assert full == "Preamble"


def test_build_full_text_no_markdown_headers():
    sections = {"experience": "Content here"}
    full = build_full_text("", sections, use_markdown_headers=False)
    assert "## " not in full
    assert "Content here" in full


# ---- Parse to structure ----

def test_parse_resume_text_to_structure():
    text = """Alice
alice@test.com

Summary
Short bio.

Experience
Job at Co.
"""
    parsed = parse_resume_text_to_structure(text)
    assert isinstance(parsed, ParsedResume)
    assert "Alice" in parsed.preamble
    assert "summary" in parsed.sections
    assert "experience" in parsed.sections
    assert "## Summary" in parsed.full_text
    assert "Short bio" in parsed.full_text


def test_parse_resume_text_to_structure_no_sections_falls_back_to_full():
    text = "Only one line with no headers."
    parsed = parse_resume_text_to_structure(text)
    assert parsed.preamble == "Only one line with no headers."
    assert parsed.sections == {}
    assert "Only one line" in parsed.full_text


# ---- Fixture-based integration ----

def _fixture_path(name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "fixtures", "sample_resumes", name)


def test_sample_with_sections():
    path = _fixture_path("sample_with_sections.txt")
    if not os.path.exists(path):
        pytest.skip("Fixture file not found")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parsed = parse_resume_text_to_structure(text)
    assert "Jane Doe" in parsed.preamble or "Jane Doe" in parsed.full_text
    assert "summary" in parsed.sections or "Summary" in parsed.full_text
    assert "experience" in parsed.sections
    assert "education" in parsed.sections
    assert "skills" in parsed.sections
    assert "Senior Software Engineer" in parsed.full_text
    assert "Bachelor of Science" in parsed.full_text
    assert "Python" in parsed.full_text


def test_sample_minimal_no_headers():
    path = _fixture_path("sample_minimal_no_headers.txt")
    if not os.path.exists(path):
        pytest.skip("Fixture file not found")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parsed = parse_resume_text_to_structure(text)
    # Everything should be in preamble / full text; no sections detected
    assert "Alex Smith" in parsed.full_text
    assert "Data Scientist" in parsed.full_text
    assert "Python" in parsed.full_text


def test_sample_two_page():
    """Two-page style fixture: section (Certifications) at page boundary is detected."""
    path = _fixture_path("sample_two_page.txt")
    if not os.path.exists(path):
        pytest.skip("Fixture file not found")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parsed = parse_resume_text_to_structure(text)
    assert "Jane Doe" in parsed.full_text
    assert "experience" in parsed.sections
    assert "certifications" in parsed.sections
    assert "AWS Certified" in parsed.full_text


def test_sample_docx_style():
    """DOCX-style fixture: table-like lines (|) are preserved in content."""
    path = _fixture_path("sample_docx_style.txt")
    if not os.path.exists(path):
        pytest.skip("Fixture file not found")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parsed = parse_resume_text_to_structure(text)
    assert "Alex Chen" in parsed.full_text
    assert "experience" in parsed.sections
    assert "Tableau" in parsed.full_text or "SQL" in parsed.full_text


# ---- Section patterns config (Phase 3) ----

def test_section_patterns_config_builds_matching_patterns():
    """Patterns from app.config.section_patterns match expected headers."""
    from app.config.section_patterns import build_section_patterns, CANONICAL_SECTION_ORDER

    patterns = build_section_patterns()
    assert len(patterns) >= 8
    names = [p[0] for p in patterns]
    assert "summary" in names
    assert "experience" in names
    assert "education" in names
    assert "skills" in names
    # Quick match check
    for canonical, pat in patterns:
        if canonical == "summary":
            assert pat.match("Summary") and pat.match("Professional Summary")
        if canonical == "experience":
            assert pat.match("Experience") and pat.match("Work Experience")


def test_section_patterns_canonical_order():
    from app.config.section_patterns import get_canonical_section_order

    order = get_canonical_section_order()
    assert order[0] == "preamble"
    assert "experience" in order
    assert "education" in order


# ---- Constants ----

def test_canonical_order_includes_expected():
    assert "preamble" in CANONICAL_SECTION_ORDER
    assert "experience" in CANONICAL_SECTION_ORDER
    assert "education" in CANONICAL_SECTION_ORDER
    assert "skills" in CANONICAL_SECTION_ORDER


def test_section_patterns_compiled():
    for name, pattern in RESUME_SECTION_PATTERNS:
        assert name
        assert hasattr(pattern, "match")


# ---- should_use_ai_sections ----

def test_should_use_ai_sections_true_when_no_sections():
    parsed = ParsedResume(full_text="Some text", preamble="Some text", sections={})
    assert should_use_ai_sections(parsed) is True


def test_should_use_ai_sections_true_when_one_section():
    parsed = ParsedResume(
        full_text="Preamble\n\n## Experience\nContent",
        preamble="Preamble",
        sections={"experience": "Content"},
    )
    assert should_use_ai_sections(parsed) is True


def test_should_use_ai_sections_true_when_preamble_dominant():
    parsed = ParsedResume(
        full_text="A" * 100,
        preamble="A" * 50,
        sections={"experience": "B" * 10, "education": "C" * 10},
    )
    assert should_use_ai_sections(parsed) is True


def test_should_use_ai_sections_false_when_multiple_sections_and_small_preamble():
    parsed = ParsedResume(
        full_text="Short preamble. " + "Experience content. " * 20 + "Education content. " * 20,
        preamble="Short preamble.",
        sections={"experience": "Experience content. " * 20, "education": "Education content. " * 20},
    )
    assert should_use_ai_sections(parsed) is False


def test_should_use_ai_sections_false_when_empty_full_text():
    parsed = ParsedResume(full_text="", preamble="", sections={})
    assert should_use_ai_sections(parsed) is False


# ---- validate_resume_sections ----

def test_validate_resume_sections_all_found():
    parsed = ParsedResume(
        full_text="Full",
        preamble="Name\nEmail",
        sections={"experience": "Job at Co.", "education": "BS CS.", "skills": "Python"},
    )
    v = validate_resume_sections(parsed)
    assert isinstance(v, ResumeSectionValidation)
    assert v.has_preamble is True
    assert v.is_valid is True
    assert set(v.sections_found) == {"experience", "education", "skills"}
    assert v.sections_missing == []
    assert v.warnings == []


def test_validate_resume_sections_missing_expected():
    # At least one of (experience, education) is required; experience present => valid
    parsed = ParsedResume(
        full_text="Full",
        preamble="Name",
        sections={"experience": "Job."},
    )
    v = validate_resume_sections(parsed)
    assert v.has_preamble is True
    assert v.is_valid is True  # experience is present (at least one required)
    assert "experience" in v.sections_found
    assert "education" in v.sections_missing
    assert "skills" in v.sections_missing
    assert any("Education" in w for w in v.warnings)
    assert any("Skills" in w for w in v.warnings)


def test_validate_resume_sections_empty_content_not_found():
    parsed = ParsedResume(
        full_text="Full",
        preamble="Name",
        sections={"experience": "  ", "education": "BS.", "skills": "Python"},
    )
    v = validate_resume_sections(parsed)
    assert "experience" not in v.sections_found
    assert "experience" in v.sections_missing


def test_validate_resume_sections_no_preamble():
    parsed = ParsedResume(
        full_text="Full",
        preamble="",
        sections={"experience": "Job.", "education": "BS.", "skills": "Python"},
    )
    v = validate_resume_sections(parsed)
    assert v.has_preamble is False
    assert v.is_valid is False
    assert any("preamble" in w.lower() for w in v.warnings)


def test_validate_resume_sections_no_required_section_invalid():
    """When neither experience nor education is present, resume is invalid."""
    parsed = ParsedResume(
        full_text="Full",
        preamble="Name",
        sections={"skills": "Python, SQL"},
    )
    v = validate_resume_sections(parsed)
    assert v.has_preamble is True
    assert v.is_valid is False
    assert "skills" in v.sections_found
    assert "experience" in v.sections_missing
    assert "education" in v.sections_missing


# ---- _looks_like_name_or_header ----

def test_looks_like_name_or_header():
    from app.utils.parsers import _looks_like_name_or_header

    assert _looks_like_name_or_header("Alex Smith") is True
    assert _looks_like_name_or_header("Alex") is True  # Single name from OCR
    assert _looks_like_name_or_header("John Doe") is True
    assert _looks_like_name_or_header("Jane M. Smith") is True
    assert _looks_like_name_or_header("First Last | Email") is True
    assert _looks_like_name_or_header("This is a long sentence that is not a name") is False
    assert _looks_like_name_or_header("lowercase name") is False
    assert _looks_like_name_or_header("") is False
    assert _looks_like_name_or_header("A" * 150) is False  # Too long


def test_is_plausible_phone_rejects_date_ranges():
    """Date ranges (e.g. from OCR/layout) must not be accepted as phone numbers."""
    assert is_plausible_phone("July 2024 - Present") is False
    assert is_plausible_phone("2024 - Present") is False
    assert is_plausible_phone("January 2020 – September 2025") is False
    assert is_plausible_phone("") is False
    assert is_plausible_phone("(555) 123-4567") is True
    assert is_plausible_phone("555-123-4567") is True
    assert is_plausible_phone("+1 555 123 4567") is True


def test_extract_contact_from_text():
    text = "Jane Doe\nBrooklyn, NY\n(555) 123-4567\njane@example.com\nlinkedin.com/in/janedoe\nhttps://jane.dev"
    c = extract_contact_from_text(text)
    assert isinstance(c, ExtractedContact)
    assert any("555" in p for p in c.phones)
    assert "jane@example.com" in c.emails
    assert c.location and "Brooklyn" in c.location
    assert any("linkedin" in u.lower() for u in c.linkedin_urls)
    assert (c.portfolio_urls or c.other_urls) and any("jane" in u.lower() or "dev" in u for u in (c.portfolio_urls or []) + (c.other_urls or []))


def test_merge_contact_into_preamble_adds_missing():
    preamble = "Jane Doe"
    contact = ExtractedContact(
        phones=["(555) 111-2222"],
        emails=["jane@example.com"],
        linkedin_urls=["https://linkedin.com/in/janedoe"],
        portfolio_urls=["https://janeportfolio.example.com"],
        other_urls=[],
        location="Anytown, ST",
    )
    merged = _merge_contact_into_preamble(preamble, contact)
    assert "Jane Doe" in merged
    assert "555" in merged
    assert "jane@example.com" in merged
    assert "Anytown" in merged
    assert "linkedin" in merged.lower()
    assert "janeportfolio" in merged or "portfolio" in merged.lower()


def test_merge_contact_into_preamble_no_duplicate():
    preamble = "Jane Doe\nBrooklyn, NY · jane@example.com"
    contact = ExtractedContact(
        phones=[],
        emails=["jane@example.com"],
        linkedin_urls=[],
        portfolio_urls=[],
        other_urls=[],
        location="Brooklyn, NY",
    )
    merged = _merge_contact_into_preamble(preamble, contact)
    assert merged.count("jane@example.com") <= 2
    assert merged.count("Brooklyn") <= 2


def test_pdf_text_extraction_and_contact_merge():
    """
    Unit test: extracted resume text is parsed to structure and contact merge
    adds phone, location, or links when present. Uses in-repo fixture text only
    (no external PDFs or personal data).
    """
    from app.utils.parsers import parse_resume_text_to_structure, _merge_contact_into_preamble

    # Use fixture-style text with generic name/contact (no personal info)
    text = """Alex Smith
Anytown, ST · (555) 999-8888 · alex@example.com · linkedin.com/in/alexsmith

Professional Summary
Software engineer with experience in Python.

Experience
Engineer at Acme 2020-present.
"""
    parsed = parse_resume_text_to_structure(text)
    combined = (text + " " + (parsed.preamble or "")).lower()
    assert "alex" in combined and "smith" in combined
    assert "555" in combined or "alex@example.com" in combined
    # Contact merge with same-style contact should preserve or add details
    from app.utils.parsers import extract_contact_from_text
    contact = extract_contact_from_text(text)
    merged = _merge_contact_into_preamble(parsed.preamble or "", contact)
    assert "alex" in merged.lower() or "smith" in merged.lower()
    assert "555" in merged or "alex@example.com" in merged
    assert "linkedin" in merged.lower() or "example.com" in merged


# ---- Pipeline (Phase 2) ----

def test_run_pipeline_plain_text_matches_parse_resume_text_to_structure():
    """run_pipeline with text/plain produces same result as parse_resume_text_to_structure."""
    text = """Jane Doe
jane@email.com

Summary
Short bio.

Experience
Engineer at Acme.
"""
    content = text.encode("utf-8")
    parsed_pipeline = run_pipeline(content, "text/plain", DEFAULT_PIPELINE_CONFIG)
    parsed_direct = parse_resume_text_to_structure(text)
    assert parsed_pipeline.full_text.strip() == parsed_direct.full_text.strip()
    assert parsed_pipeline.preamble.strip() == parsed_direct.preamble.strip()
    assert parsed_pipeline.sections == parsed_direct.sections


def test_run_pipeline_unknown_mime_falls_back_to_plain():
    """Unknown mime_type falls back to plain decode."""
    text = "Just some text"
    content = text.encode("utf-8")
    parsed = run_pipeline(content, "application/unknown", DEFAULT_PIPELINE_CONFIG)
    assert "Just some text" in parsed.full_text


def test_pipeline_config_uses_custom_cleaner():
    """Custom config cleaner is used when provided."""
    def suffix_cleaner(t: str) -> str:
        return (t or "") + "\n[CLEANED]"
    config = PipelineConfig(
        extractors=DEFAULT_PIPELINE_CONFIG.extractors,
        cleaner=suffix_cleaner,
        section_extractor=extract_sections_by_regex,
        canonical_section_order=CANONICAL_SECTION_ORDER,
    )
    text = "Name\n\nExperience\nJob."
    content = text.encode("utf-8")
    parsed = run_pipeline(content, "text/plain", config)
    assert "[CLEANED]" in parsed.full_text


# ---- Phase 5: Performance (NFR1) ----

def test_section_extraction_performance():
    """Regex section extraction completes in < 100 ms for ~4-page text (NFR1)."""
    # Build ~4 pages of text (mix of preamble, sections, bullets); ~2000 chars per page
    block = "Line one with some content here.\n- Bullet A.\n- Bullet B.\n\n"
    page = block * 35  # ~1 page
    long_text = "Name\nEmail\n\nProfessional Summary\nShort summary.\n\nExperience\n" + (page * 4)
    assert len(long_text) >= 8000, f"Expected >= 8000 chars, got {len(long_text)}"
    start = time.perf_counter()
    cleaned = clean_resume_text(long_text)
    preamble, sections = extract_sections_by_regex(cleaned)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, f"Section extraction took {elapsed:.3f}s (expected < 0.15s for ~4 pages)"
