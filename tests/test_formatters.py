import pytest
from app.utils.formatters import (
    format_contact_info,
    format_skills_section,
    format_experience_section,
    format_education_section,
    format_certifications_section,
    _clean_headline,
    _is_headline,
    build_markdown_resume
)
from app.utils.parsers import ExtractedContact

def test_format_contact_info():
    contact = ExtractedContact(
        phones=["123-456-7890"],
        emails=["test@example.com"],
        location="New York, NY",
        linkedin_urls=["linkedin.com/in/test"],
        portfolio_urls=["github.com/test"],
        other_urls=[],
        security_clearance="Top Secret"
    )
    result = format_contact_info("John Doe", contact)
    
    assert "# John Doe" in result
    assert "New York, NY" in result
    assert "Top Secret" in result
    assert "123-456-7890" in result
    assert "test@example.com" in result
    assert "linkedin.com/in/test" in result
    assert "github.com/test" in result
    assert " · " in result

def test_format_contact_info_empty():
    contact = ExtractedContact([], [], [], [], [], None, None)
    result = format_contact_info("", contact)
    assert result == "# Candidate Name"

def test_clean_headline():
    assert _clean_headline("Software Engineer | 2020 - 2022") == "**Software Engineer** | 2020 - 2022"
    assert _clean_headline("Software Engineer, Google | 2020 - 2022") == "**Software Engineer**, Google | 2020 - 2022"
    assert _clean_headline("**Already Bold** | 2020") == "**Already Bold** | 2020"
    assert _clean_headline("- Software Engineer | 2020") == "**Software Engineer** | 2020"

def test_is_headline_bolding():
    # Should recognize pipe as a headline even if it starts with **
    assert _is_headline("**Machine Learning Engineer**, Welldoc | FEB 2026 – PRESENT") is True
    assert _is_headline("**Senior Data Scientist**, Nucleix, San Diego, CA | MAR 2024 – AUG 2025") is True
    
    # Standard bullet points should not be headlines
    assert _is_headline("- **Designed**, implemented, and deployed a pipeline") is False
    assert _is_headline("* **Designed** something") is False

def test_format_skills_section():
    raw_skills = """
    Languages: Python, Java
    - Frameworks: React, Django
    [Tools]: Git, Docker
    """
    result = format_skills_section(raw_skills)
    assert "**Languages**: Python, Java" in result
    assert "**Frameworks**: React, Django" in result
    assert "**Tools**: Git, Docker" in result

def test_format_experience_section():
    raw_experience = """
    Software Engineer, Tech Corp | 2020 - Present
    Developed amazing features
    - Fixed bugs
    * Wrote tests
    """
    result = format_experience_section(raw_experience)
    lines = result.split("\\n")
    assert "**Software Engineer**, Tech Corp | 2020 - Present" in result
    assert "- Developed amazing features" in result
    assert "- Fixed bugs" in result
    assert "- Wrote tests" in result

def test_format_education_section():
    raw_education = """
    B.S. Computer Science, University X | 2015 - 2019
    - GPA: 3.9
    Minor in Math
    """
    result = format_education_section(raw_education)
    assert "**B.S. Computer Science**, University X | 2015 - 2019" in result
    # Education entries use the same header + bullet structure as experience.
    assert "- GPA: 3.9" in result
    assert "- Minor in Math" in result

def test_format_certifications_section():
    raw_certs = """
    AWS Certified Solutions Architect | 2021
    - Certified Kubernetes Administrator
    """
    result = format_certifications_section(raw_certs)
    assert "**AWS Certified Solutions Architect** | 2021" in result
    assert "**Certified Kubernetes Administrator** |" in result

def test_build_markdown_resume_recovers_summary():
    from app.utils.parsers import ParsedResume
    res = ParsedResume(
        full_text="...",
        preamble="Ofir Shliefer\nGaithersburg, MD · 973-800-9119\nAccomplished data professional with over 7 years of experience in statistical data analysis, architecting robust ETL pipelines, and productionizing machine learning models.",
        sections={"experience": "Job"}
    )
    contact = ExtractedContact(phones=["973-800-9119"], emails=[], location="Gaithersburg, MD", linkedin_urls=[], portfolio_urls=[], other_urls=[], security_clearance=None)
    
    md = build_markdown_resume(res, contact, "Ofir Shliefer")
    
    # Summary should be extracted into its own section
    assert "## Summary" in md
    assert "Accomplished data professional with over 7 years of experience" in md
    assert "## Experience" in md
