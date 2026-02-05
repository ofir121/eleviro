"""
Resume section header patterns: canonical names and regex pattern strings.
Load at startup or first use; parsers compile these into RESUME_SECTION_PATTERNS.
Add or edit entries here to support new sections or header variants without touching parser logic.
"""
import re
from typing import Dict, List, Tuple

# Canonical order for reassembling full text (preamble is implicit first).
CANONICAL_SECTION_ORDER: List[str] = [
    "preamble",
    "summary",
    "experience",
    "education",
    "skills",
    "publications",
    "certifications",
    "projects",
    "awards",
    "other",
]

# Canonical name -> list of header variants (matched as whole line, case-insensitive, optional trailing . or :).
# Order does not matter; variants are combined into one regex per section.
SECTION_HEADER_VARIANTS: Dict[str, List[str]] = {
    "summary": [
        "Professional Summary",
        "Summary",
        "Profile",
        "Objective",
        "About Me",
        "Executive Summary",
        "Career Summary",
    ],
    "experience": [
        "Work Experience",
        "Experience",
        "Employment History",
        "Professional Experience",
        "Career History",
        "Employment",
    ],
    "education": [
        "Education",
        "Academic",
        "Qualifications",
        "Qualification",
        "Degrees",
        "Degree",
        "Academic Background",
    ],
    "skills": [
        "Technical Skills",
        "Skills",
        "Core Competencies",
        "Expertise",
        "Technologies",
        "Key Skills",
        "Competencies",
    ],
    "publications": [
        "Publications",
        "Publication",
        "Research",
        "Papers",
        "Paper",
        "Selected Publications",
        "Selected Publication",
    ],
    "certifications": [
        "Certifications",
        "Certification",
        "Licenses",
        "License",
        "Certificates",
        "Certificate",
        "Professional Development",
    ],
    "projects": [
        "Key Projects",
        "Key Project",
        "Projects",
        "Project",
        "Notable Projects",
        "Notable Project",
    ],
    "awards": [
        "Awards",
        "Award",
        "Honors",
        "Honor",
        "Achievements",
        "Achievement",
        "Recognition",
    ],
    "other": [
        "Additional",
        "Other",
        "Activities",
        "Volunteer",
        "Interests",
        "Interest",
        "Languages",
        "Language",
        "References",
        "Reference",
    ],
}


def build_section_patterns(
    variants: Dict[str, List[str]] = None,
    order: List[str] = None,
) -> List[Tuple[str, re.Pattern]]:
    """
    Build (canonical_name, compiled_pattern) list from variant strings.
    Pattern matches whole line with optional trailing . or : (case-insensitive).
    """
    variants = variants or SECTION_HEADER_VARIANTS
    order = order or CANONICAL_SECTION_ORDER
    result: List[Tuple[str, re.Pattern]] = []
    for canonical in order:
        if canonical == "preamble":
            continue
        if canonical not in variants:
            continue
        parts = [re.escape(v.strip()) for v in variants[canonical] if v and v.strip()]
        if not parts:
            continue
        # Whole line, optional trailing punctuation
        pattern_str = r"^\s*(?:" + "|".join(parts) + r")\s*[.:]?\s*$"
        result.append((canonical, re.compile(pattern_str, re.I)))
    return result


def get_canonical_section_order() -> List[str]:
    """Return the canonical section order (for use by parsers/build_full_text)."""
    return list(CANONICAL_SECTION_ORDER)


def get_section_header_variants() -> Dict[str, List[str]]:
    """Return copy of section header variants (for config UI or overrides)."""
    return {k: list(v) for k, v in SECTION_HEADER_VARIANTS.items()}
