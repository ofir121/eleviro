# Resume Parser – Design

## Overview
The parser improves resume handling in two layers:
1. **Layer 1 – Text extraction and cleaning**: Better raw text from PDF/DOCX and a single cleanup pipeline.
2. **Layer 2 – Section structure**: Regex-based section detection first; optional AI to fix misattributed or ambiguous content and to extract subsections.

The public API remains: `parse_pdf(file)` and `parse_docx(file)` returning a single string. Internally we optionally build that string from a structured section map so that section order and boundaries are consistent.

## Architecture

```
Upload (PDF/DOCX)
       │
       ▼
┌──────────────────┐
│ Raw extraction   │  PDF: pypdf (layout mode fallback) / DOCX: existing recursive
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ clean_*_text()   │  Join broken lines, normalize spaces, preserve bullets/paragraphs
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ extract_sections_│  Regex over lines; build section_name → content map
│ by_regex()       │  Standard section order applied when rebuilding full text
└────────┬─────────┘
         │
         ├──► sections: Dict[str, str]   (for optional structured API / future use)
         │
         ▼
┌──────────────────┐     (optional, when enabled)
│ AI subsection /  │  Only for ambiguous blocks or “subsection” labels
│ fix sections    │  Input: section map or orphan lines; output: corrected map
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ build_full_text()│  Concatenate preamble + sections in canonical order
└────────┬─────────┘
         │
         ▼
   full_text: str  →  format_resume / extract_candidate_info / adapt_resume
```

**Pipeline and config (Phase 2–3):** `run_pipeline(content, mime_type, config)` runs extract → clean → section extract → contact merge → build. Section patterns live in `app.config.section_patterns`; new formats can be added by registering an extractor in `PipelineConfig.extractors`. See README “Adding a new section pattern” and “Adding a new format”.

## 1. Text Extraction

### PDF
- Prefer `page.extract_text(extraction_mode="layout")` when available (pypdf 3.x+) to improve reading order and reduce mid-word breaks.
- Fallback to default `extract_text()` if layout raises or returns empty.
- Then run a single `clean_pdf_text(text)` pass (see below).

### DOCX
- Keep existing `get_text_recursive(doc)` to include body, tables, and text boxes.
- Add a `clean_docx_text(text)` (or reuse a shared cleaner) so that DOCX output goes through the same normalization as PDF (join broken lines, normalize spaces, preserve bullets/paragraphs).

### Cleaning (shared ideas)
- Normalize horizontal whitespace: `\t` → space, collapse multiple spaces to one.
- Join lines that are clearly continuations: line N doesn’t end with sentence-ending punctuation and line N+1 doesn’t start with a section header or bullet → join with space.
- Preserve: blank lines (paragraph break), lines starting with `-`, `*`, `•`, or `\d+\.`, and lines that match section header regex (so we don’t merge a header with the previous line).
- Final: collapse 3+ newlines to 2, trim.

## 2. Section Detection (Regex)

### Canonical section names and patterns
Map normalized names used in code and output to a list of regex patterns that match common headers (case-insensitive, strip trailing colon/period). Examples:

| Canonical name  | Example patterns (regex) |
|-----------------|--------------------------|
| summary         | Professional Summary, Summary, Profile, Objective, About Me, Executive Summary |
| experience      | Experience, Work Experience, Employment, Professional Experience, Career |
| education       | Education, Academic, Qualifications, Degrees |
| skills          | Skills, Technical Skills, Core Competencies, Expertise, Technologies |
| publications    | Publications, Research, Papers |
| certifications  | Certifications, Licenses, Certificates |
| projects        | Projects, Key Projects |
| awards          | Awards, Honors, Achievements |
| other           | Additional, Other, Activities, Volunteer, Interests |

Implementation: a list of `(canonical_name, re.Pattern)` or a dict. A line is a section header if it matches one of these patterns and is “header-like” (e.g. short, no long runs of lowercase, or explicitly allow all-caps short lines).

### Algorithm
1. Split cleaned text into lines (and optionally merge lines that were joined incorrectly for headers – e.g. “EXPERIENCE Work” should not become one line if “EXPERIENCE” is a known header).
2. Iterate line by line:
   - If line matches a section pattern → start new section with that canonical name; content so far (since previous header) is appended to the previous section (or to “preamble” if no previous header).
   - Else → append line to current section (with newline).
3. After the loop, assign any remaining buffer to the last section or preamble.
4. Build `sections: Dict[str, str]` and a `preamble: str`.

### Order for reassembly
Define a canonical order, e.g.:  
`preamble, summary, experience, education, skills, publications, certifications, projects, awards, other`.  
Any section not in this list appears at the end in discovery order when building full text.

## 3. AI Use (Optional and Conditional)

- **When**: The caller sets `use_ai_sections=True` **and** `should_use_ai_sections(parsed)` is True. AI is **not** used when regex section detection is already strong.
- **Condition** (`should_use_ai_sections(parsed)` in `app.utils.parsers`):
  - **Use AI** when:
    - No sections detected (all content in preamble), or
    - Only one section detected (poor split), or
    - Preamble is disproportionately large (preamble length / full_text length > `PREAMBLE_RATIO_THRESHOLD_FOR_AI`, default 0.45).
  - **Do not use AI** when: multiple sections are present and preamble is a small fraction of total content (regex result is trusted).
- **Input**: Full resume text and optionally the current `sections` map (for refinement).
- **Prompt**: Ask the model to return a JSON mapping section names to content, or to refine assignment. Instruct: do not add or remove factual content; only assign/label.
- **Output**: Single full-text string with `## Section Name` boundaries, used as the resume input for format_resume / adapt_resume.

Subsections (e.g. “Technical” vs “Languages” under Skills) can be requested in the same AI call; the pipeline still emits one block per canonical section for downstream use.

## 4. Output

- **Primary**: `full_text: str` = `build_full_text(preamble, sections)` with optional `## Section Name` markers so the string is clearly structured for the existing AI.
- **Optional**: A small dataclass or dict, e.g. `ParsedResume(full_text=..., sections={...}, preamble=...)` for future endpoints or section-specific features. The current API continues to return only `full_text` from `parse_pdf` / `parse_docx`.

## 5. Configuration

- **use_ai_sections**: bool (default False) – whether to call AI to fix or refine sections/subsections.
- **Section patterns:** `app.config.section_patterns` — `CANONICAL_SECTION_ORDER`, `SECTION_HEADER_VARIANTS`; compiled via `build_section_patterns()`.
- **Pipeline:** `PipelineConfig` in `parsers.py` — extractors (by mime_type), cleaner, section_extractor, canonical_section_order. Default: `DEFAULT_PIPELINE_CONFIG`.

## 6. Testing Strategy

- **Unit tests (no I/O)**:
  - `clean_pdf_text` / shared cleaner: given a string with broken lines and bullets, assert joined lines and preserved breaks.
  - `extract_sections_by_regex`: given a string with known headers, assert `sections` and `preamble` match expected.
  - `build_full_text`: given a section map, assert order and presence of `##` markers (if used).
- **Integration tests (with fixtures)**:
  - Use 1–2 sample resume texts (saved as .txt or embedded strings from real PDF extractions) and assert that key sections (e.g. Experience, Education) are detected and that full text contains all content.
- **Regression**: Run parser on the two example PDFs (when available in CI) and snapshot or assert minimal expected sections.

## 7. Files to Add/Change

| File | Change |
|------|--------|
| `app/utils/parsers.py` | Add layout PDF extraction; shared cleaner; regex section patterns; `extract_sections_by_regex()`; `build_full_text()`; optional `ParsedResume`; keep `parse_pdf`/`parse_docx` returning str, built from sections when possible. |
| `app/services/ai_service.py` | Add `parse_resume_sections_with_ai(resume_text: str, sections: dict) -> dict` (or similar) for optional subsection/fix pass. |
| `app/routers/job_router.py` | No change required if parser still returns str; optional: pass `use_ai_sections` from request. |
| `tests/test_parsers.py` | New: tests for cleaning, section regex, build_full_text, and one full parse from sample text. |
| `tests/fixtures/sample_resumes/` | 1–2 .txt files with sample resume content for tests. |
