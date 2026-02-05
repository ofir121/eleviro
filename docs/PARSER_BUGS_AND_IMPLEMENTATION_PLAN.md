# Resume Parser – Bug List & Implementation Plan

This document lists identified bugs, design limitations, and a structured implementation plan to make the resume parser bulletproof, adaptive, and modular across different resume formats.

---

## 1. Bug List

### 1.1 Preamble blank lines dropped (FR1.2, FR2.3)

**Location:** `app/utils/parsers.py` – `extract_sections_by_regex()`

**Issue:** Blank lines in the preamble (content before the first section header) are discarded. When `stripped` is empty we `continue` without appending anything to `preamble_parts`, so paragraph breaks in the header block (e.g. name, then blank, then contact) are lost.

**Impact:** Preamble formatting is flattened; downstream formatting/AI may see "NameContact" style runs. Low severity for content completeness, medium for structure fidelity.

**Repro:**
```python
text = "Jane Doe\n\njane@email.com\n\nProfessional Summary\n..."
preamble, _ = extract_sections_by_regex(text)
# preamble is "Jane Doe\njane@email.com" – blank line between name and email is lost
```

---

### 1.2 Blank line handling when `current_section` is None

**Location:** `app/utils/parsers.py` – `extract_sections_by_regex()` loop

**Issue:** For empty lines we do `current_content.append("")` even when `current_section is None`. That appends to the same `current_content` list that is later reset when we enter the first section. So we both (a) never record blanks in the preamble, and (b) briefly pollute `current_content` with `""` before resetting it. Logic is confusing and preamble blanks are still lost.

**Fix direction:** Explicitly handle “in preamble” vs “in section”: when in preamble, append a sentinel or preserve blanks in `preamble_parts` (e.g. append `""` to `preamble_parts` for blank lines so `"\n".join(preamble_parts)` keeps paragraph breaks).

---

### 1.3 Duplicate section headers – content merge correctness

**Location:** `app/utils/parsers.py` – `extract_sections_by_regex()`, `flush_current()`

**Status:** Currently correct. When the same canonical section (e.g. "Experience") appears twice, the second block is appended to the first via `existing + "\n" + "\n".join(current_content)`. No bug here; leaving as a note for regression tests.

**Recommendation:** Add an explicit test: resume with two "Experience" headers and assert both blocks appear in `sections["experience"]`.

---

### 1.4 Apply suggestions: first-match-only replacement

**Location:** `app/routers/job_router.py` – `apply_suggestions_to_text()`

**Issue:** Each suggestion is applied with `re.sub(..., count=1)`, so only the first occurrence of the pattern is replaced. If the same bullet text appears in two places (e.g. "Led the team" in two roles), only the first is updated. There is no section or position awareness.

**Impact:** User may accept a suggestion expecting it to apply to a specific instance or to all instances; behavior is ambiguous.

**Fix direction:** Either (1) document that only the first match is replaced, and/or (2) add optional section hint from `ResumeSuggestion.section` and restrict replacement to that section’s text, or (3) support “replace all” vs “replace one” with position/section metadata from the suggestion pipeline.

---

### 1.5 Suggestion matching: whitespace-normalized but structure-agnostic

**Location:** `app/routers/job_router.py` – `apply_suggestions_to_text()`

**Issue:** Pattern is built by splitting `original_text` on `\s+` and joining with `\s+`, so any sequence of spaces/newlines matches. That can cause accidental matches across line boundaries (e.g. end of one bullet and start of another) or in the wrong section if the same phrase appears in Summary and Experience.

**Fix direction:** Prefer matching within section boundaries when `section` is available (e.g. split `original_resume` by `## ` and search only in the section indicated by the suggestion). Fall back to full-text match if section is missing or not found.

---

### 1.6 DOCX: nested tables and text box order

**Location:** `app/utils/parsers.py` – `get_text_recursive()`

**Issue:** For DOCX, body and tables are traversed in DOM order. Nested tables and text boxes may not follow visual reading order (e.g. sidebar then main column). No explicit “reading order” or layout awareness.

**Impact:** Resumes with sidebars or multi-column layouts may have jumbled section order.

**Fix direction:** (1) Document as limitation; (2) optionally add a “layout hint” pass (e.g. by vertical position if we had coordinates) or (3) rely on AI section refinement when `use_ai_sections` is true and regex order is poor.

---

### 1.7 PDF: single-page join with `\n` only

**Location:** `app/utils/parsers.py` – `_extract_pdf_text_from_reader()`

**Issue:** Pages are joined with `"\n".join(text_parts)`. There is no explicit page boundary (e.g. `\n\n`) between pages, so end of page 1 and start of page 2 can look like one paragraph.

**Impact:** Section detection and “preamble vs body” split can be wrong if a section header is at the top of page 2 and the last line of page 1 is not a natural break.

**Fix direction:** Join pages with `"\n\n"` (or a configurable separator) so page boundaries are preserved; optionally add a `PAGE_BREAK` token for downstream use.

---

### 1.8 AI section refinement: JSON key normalization

**Location:** `app/services/ai_service.py` – `parse_resume_sections_with_ai()`

**Issue:** We build output with `data.get(key, "")` for keys in `order` and then iterate `data.items()` for extras. If the model returns keys with different casing or spaces (e.g. "Professional Experience" instead of "experience"), they appear as “other” at the end and may get wrong `## ` titles.

**Fix direction:** Normalize keys to canonical names (e.g. lowercase, map "Professional Experience" → "experience") before building `parts`, and log or track unmapped keys for tuning prompts.

---

### 1.9 Empty or corrupt file handling

**Location:** `app/utils/parsers.py` – `parse_pdf`, `parse_docx`; router

**Status:** Empty/corrupt files lead to `ParsedResume(full_text="", ...)` and the router raises HTTP 400 with “Could not extract text from inputs.” So behavior is acceptable. Optional improvement: distinguish “empty file” vs “unsupported/corrupt” in error detail for better UX.

---

### 1.10 Contact merge: possible duplicate line

**Location:** `app/utils/parsers.py` – `_merge_contact_into_preamble()`

**Issue:** We build `extra_line` from items “not already in preamble” and append `"\n\n" + extra_line`. If the preamble already contains the same contact in a different format (e.g. “(555) 123-4567” vs “555-123-4567”), we might still add the extracted form and get two similar lines.

**Mitigation:** `already_in_preamble` does normalized and protocol-stripped checks; risk is reduced but not zero for all formats. Consider fuzzy or normalized comparison for phone (digits-only) and email (lowercase).

---

## 2. Design / Robustness Issues

### 2.1 Section patterns are hardcoded and English-centric

- All section headers are in one list in `parsers.py`. Adding a new section (e.g. “Patent”, “Teaching”) or supporting another language requires code changes.
- **Direction:** Make section patterns configurable (e.g. load from config or a small DSL) and keep canonical names and order in one place. Optional: pluggable “pattern provider” for i18n or vertical-specific resumes.

### 2.2 No explicit pipeline abstraction

- Flow is: extract → clean → sections → (optional AI) → build full text. Each step is a function, but there is no single “pipeline” object that allows swapping extractors (PDF vs DOCX vs plain text), cleaners, or section strategies.
- **Direction:** Introduce a small pipeline (e.g. `ResumeParsePipeline` with steps: extractor, cleaner, section_extractor, optional ai_refiner, builder) so new formats or strategies can be added without touching `parse_pdf`/`parse_docx` internals.

### 2.3 Section validation is strict (“expected” sections)

- `EXPECTED_SECTIONS = ("experience", "education", "skills")` marks resumes as invalid if any of these are missing. Some resumes are skills-only or education-only (e.g. students).
- **Direction:** Make expectations configurable or tiered (e.g. “strongly expected” vs “optional”), or add a “resume type” hint so validation rules can vary (e.g. student vs senior).

### 2.4 No schema or version for `ParsedResume`

- `ParsedResume` is a dataclass with `full_text`, `preamble`, `sections`. If we add fields (e.g. `page_breaks`, `confidence`, `language`), clients may break. No version field.
- **Direction:** Add an optional `version` or `schema_version` field and document compatibility; consider Pydantic for validation and future API use.

### 2.5 Suggestion model has no position or anchor

- `ResumeSuggestion` has `section`, `original_text`, `suggested_text` but no character offset, line number, or stable anchor. So apply logic relies on full-text search and can mis-apply when the same text appears multiple times.
- **Direction:** When generating suggestions, optionally include section name + offset or a short context anchor (e.g. first 50 chars of the section). Use this in `apply_suggestions_to_text` to target the right occurrence.

---

## 3. Implementation Plan

### Phase 1: Bug fixes (no API change)

| Priority | Item | Action | Status |
|----------|------|--------|--------|
| P0 | Preamble blank lines | In `extract_sections_by_regex`, when `current_section is None` and line is blank, append `""` to `preamble_parts` so `"\n".join(preamble_parts)` preserves blanks. | **Done** |
| P0 | Blank-line logic clarity | Only append to `current_content` when `current_section is not None`; in preamble branch explicitly append to `preamble_parts` (including `""` for blank lines). | **Done** (same fix) |
| P1 | PDF page separator | In `_extract_pdf_text_from_reader`, join page texts with `"\n\n"` (or configurable constant) so section boundaries at page breaks are clear. | **Done** |
| P1 | AI section keys | In `parse_resume_sections_with_ai`, normalize AI-returned keys to canonical names (lowercase, strip, map known variants) before building full text. | **Done** |
| P2 | Apply-suggestions doc | Document in code and/or API that “one replacement per suggestion (first match)”; optionally add a test that two identical bullets result in one replacement. | **Done** |
| P3 | Section-aware apply | When resume has `## Section` headers and suggestion has `section`, restrict replacement to that section. | **Done** |

**Deliverables:** Tests for preamble blanks, duplicate “Experience” sections, and PDF two-page fixture; all existing tests passing. **(Preamble + duplicate-section tests added; PDF separator implemented.)**

---

### Phase 2: Modular pipeline (internal refactor)

| Step | Description | Status |
|------|-------------|--------|
| 2.1 | Define a **pipeline config** (e.g. dataclass or dict): extractor name, cleaner name, section strategy (`regex` \| `ai` \| `hybrid`), canonical section order, optional AI threshold. | **Done** |
| 2.2 | Introduce **extractor interface**: `def extract(raw: bytes, mime_type: str) -> str`. Implement `PdfExtractor`, `DocxExtractor`, `PlainTextExtractor` (no-op read). | **Done** |
| 2.3 | Keep **cleaner** as a single function (or small interface) so it can be swapped later (e.g. language-specific). | **Done** |
| 2.4 | **Section extractor** interface: `def extract_sections(text: str) -> Tuple[str, Dict[str, str]]`. Current regex implementation is the default; optional wrapper that calls AI when `should_use_ai_sections` and merges. | **Done** (regex default; AI still in router) |
| 2.5 | **Builder**: keep `build_full_text(preamble, sections, ...)` as the single place that produces `full_text` from structure. | **Done** |
| 2.6 | `parse_pdf` / `parse_docx` become thin wrappers: build pipeline from config, run extract → clean → sections → (optional AI) → build → contact merge, return `ParsedResume`. | **Done** |

**Deliverables:** Pipeline runs in-process with same behavior as today; no change to router or `ParsedResume` shape. New formats (e.g. RTF) can be added by adding an extractor and wiring it in config.

---

### Phase 3: Adaptive behavior and configuration

| Step | Description | Status |
|------|-------------|--------|
| 3.1 | **Section patterns config:** Move `RESUME_SECTION_PATTERNS` and `CANONICAL_SECTION_ORDER` to a config file or module (e.g. `app/config/section_patterns.py`) with a simple format (canonical name → list of regex strings). Load at startup or first use. | **Done** |
| 3.2 | **Validation tiers:** Replace single `EXPECTED_SECTIONS` with e.g. `REQUIRED_SECTIONS` (at least one of experience/education) and `COMMON_SECTIONS` (skills, etc.). Add `ResumeType` or similar if we want student vs professional rules later. | **Done** |
| 3.3 | **AI key normalization:** Centralize “AI section key → canonical” mapping (including common model mistakes) and use it in `parse_resume_sections_with_ai` and any future AI section output. | **Done** (Phase 1) |
| 3.4 | **Optional page breaks:** In PDF path, optionally append a token or double newline between pages and preserve it through clean/section steps so downstream can use it (e.g. “page 2” in UI). | **Done** |

**Deliverables:** Section patterns and validation rules configurable without editing core parser logic; AI section output robust to key naming.

---

### Phase 4: Suggestion application and section awareness

| Step | Description | Status |
|------|-------------|--------|
| 4.1 | **Section-aware apply:** When `original_resume` is markdown with `## Section` headers, split by `## ` and identify section names. For each suggestion with a `section` field, restrict `re.search`/`re.sub` to the corresponding segment (with fallback to full text if section not found). | **Done** |
| 4.2 | **Replace-one vs replace-all:** Add an optional flag or suggestion field (e.g. `apply_to: "first" | "all"`) and implement “replace all” by iterating over matches and replacing in reverse order (to preserve indices). | Pending |
| 4.3 | **Anchors (optional):** If AI or frontend can provide a short context string (e.g. previous line or first 30 chars of block), use it to disambiguate which occurrence to replace when there are multiple matches. | Pending |

**Deliverables:** Apply-changes behavior documented; section-aware replacement implemented and tested; optional replace-all and anchors as future-ready hooks.

---

### Phase 5: Testing and regression

| Item | Description |
|------|-------------|
| 5.1 | **Fixtures:** Add fixtures: (1) two-page PDF-like text with section on page boundary, (2) duplicate “Experience” headers, (3) preamble with blank lines, (4) minimal DOCX-style text (tables, multi-block). |
| 5.2 | **Tests:** Preamble blanks, duplicate sections, PDF page separator, AI key normalization, section-aware apply (with a mock sectioned resume). |
| 5.3 | **Performance:** Keep or add a test that regex section extraction stays under a threshold (e.g. &lt; 100 ms for ~4-page text) as per NFR1. |
| 5.4 | **Documentation:** Update PARSER_DESIGN.md with pipeline diagram and config points; add a short “Adding a new section pattern” and “Adding a new format” to README or docs. |

---

## 4. Summary

- **Bugs to fix first:** Preamble blank lines, PDF page separator, AI section key normalization, and clear documentation for apply-suggestions (first-match-only).
- **Structural improvements:** Configurable section patterns, optional pipeline abstraction, and section-aware suggestion application.
- **Adaptability:** Configuration for section patterns and validation tiers, plus optional replace-all and anchors for suggestions, will support different resume formats and use cases without hardcoded changes to the core parser.

Implementing Phase 1 and the testing parts of Phase 5 gives the highest impact with minimal API change; Phases 2–4 can be done incrementally for modularity and better behavior across formats.
