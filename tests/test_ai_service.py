"""
Tests for AI service helpers and parse_resume_sections_with_ai key normalization.
"""
import pytest

from app.services.ai_service import _normalize_ai_section_keys, _AI_CANONICAL_ORDER


def test_normalize_ai_section_keys_canonical_lowercase():
    """Canonical lowercase keys are preserved."""
    data = {"preamble": "Name", "experience": "Job at Co.", "education": "BS CS."}
    out = _normalize_ai_section_keys(data)
    assert out["preamble"] == "Name"
    assert out["experience"] == "Job at Co."
    assert out["education"] == "BS CS."


def test_normalize_ai_section_keys_variants_mapped():
    """Common AI variants map to canonical names."""
    data = {
        "Professional Summary": "Summary text",
        "Work Experience": "Experience text",
        "Technical Skills": "Python, SQL",
        "Academic": "BS CS",
    }
    out = _normalize_ai_section_keys(data)
    assert "summary" in out and out["summary"] == "Summary text"
    assert "experience" in out and out["experience"] == "Experience text"
    assert "skills" in out and out["skills"] == "Python, SQL"
    assert "education" in out and out["education"] == "BS CS"


def test_normalize_ai_section_keys_merge_duplicates():
    """Same canonical section under two keys is merged."""
    data = {
        "Experience": "First job 2020-2022.",
        "Professional Experience": "Second job 2022-present.",
    }
    out = _normalize_ai_section_keys(data)
    assert "experience" in out
    assert "First job" in out["experience"]
    assert "Second job" in out["experience"]


def test_normalize_ai_section_keys_empty_values_skipped():
    """Keys with empty or whitespace-only values are omitted."""
    data = {"preamble": "Name", "summary": "", "experience": "  ", "education": "BS."}
    out = _normalize_ai_section_keys(data)
    assert "preamble" in out
    assert "education" in out
    assert "summary" not in out
    assert "experience" not in out


def test_normalize_ai_section_keys_unknown_preserved():
    """Unknown keys are preserved with normalized form (lowercase, underscores)."""
    data = {"preamble": "Name", "Custom Section": "Some content"}
    out = _normalize_ai_section_keys(data)
    assert out["preamble"] == "Name"
    assert "custom_section" in out and out["custom_section"] == "Some content"


def test_normalize_ai_section_keys_empty_input():
    assert _normalize_ai_section_keys({}) == {}
    assert _normalize_ai_section_keys(None) == {}
