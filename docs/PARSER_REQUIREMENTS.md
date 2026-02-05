# Resume Parser – Requirements

## Purpose
The Eleviro resume parser must reliably extract and structure content from uploaded resumes (PDF and DOCX) so that:
- Downstream AI (format_resume, extract_candidate_info, adapt_resume) receives **complete, well-ordered text** with clear section boundaries.
- Section-level and subsection-level structure can be used for formatting, suggestions, and export.

## Functional Requirements

### FR1: Text extraction
- **FR1.1** Extract all text from PDF and DOCX resumes without dropping content (e.g. text in tables, text boxes, multi-column layout).
- **FR1.2** Normalize layout artifacts: join mid-sentence line breaks, collapse excessive spaces, preserve intentional paragraph and list breaks.
- **FR1.3** For PDFs, use extraction that respects reading order where possible (e.g. layout mode or fallback to default).

### FR2: Section detection (regex-first)
- **FR2.1** Detect common resume section headers via **regex patterns** (case-insensitive, optional punctuation), including but not limited to:
  - Summary / Professional Summary / Profile / Objective / About
  - Experience / Work Experience / Employment / Professional Experience / Career
  - Education / Academic / Qualifications / Degrees
  - Skills / Technical Skills / Core Competencies / Expertise
  - Publications / Research / Papers
  - Certifications / Licenses / Certificates
  - Projects / Key Projects
  - Awards / Honors / Achievements
  - Additional / Other / Activities / Volunteer
- **FR2.2** Support common header variants: all caps, title case, with or without trailing colon, with or without underline/separator on next line.
- **FR2.3** Assign content between two consecutive section headers to the first header; content before the first header is “preamble” (e.g. name, contact).

### FR3: Subsection and ambiguous content (AI when needed)
- **FR3.1** When regex section detection is uncertain or content is ambiguous, use **AI** to:
  - Assign orphan lines or blocks to the correct section.
  - Split or label subsections within a section (e.g. “Technical Skills” vs “Languages” under Skills).
- **FR3.2** AI must not invent or remove content; it may only re-label or re-order for structure.
- **FR3.3** AI subsection extraction is **optional** and can be toggled (e.g. for cost/speed vs accuracy).

### FR4: Output and compatibility
- **FR4.1** Parser must expose a **single full-text string** for backward compatibility with existing `format_resume`, `extract_candidate_info`, and `adapt_resume` flows.
- **FR4.2** Optionally expose a **structured representation** (e.g. `{ "sections": { "Experience": "...", "Education": "..." }, "full_text": "..." }`) for future use (e.g. section-specific suggestions or export).
- **FR4.3** The full-text output must include all extracted content in a consistent order (e.g. Preamble → Summary → Experience → Education → Skills → …) with clear section boundaries so that AI prompts can rely on structure.

### FR5: Robustness
- **FR5.1** Handle resumes with no detectable section headers by returning the cleaned full text and treating the whole body as one block.
- **FR5.2** Handle empty or corrupt files gracefully (return empty string or structured empty result, no uncaught exceptions).
- **FR5.3** Preserve Unicode and common symbols (bullets, middle dots, etc.) used in resumes.

## Non-Functional Requirements

### NFR1: Performance
- Regex-based section extraction should complete in &lt; 100 ms for typical resume length (~2–4 pages).
- AI subsection extraction (when enabled) should be invoked only when necessary and with bounded input size (e.g. chunk or section caps).

### NFR2: Testability
- Section regex patterns and extraction logic must be unit-testable with sample resume strings (no file I/O required for core logic).
- Provide at least two sample resume texts (e.g. from real PDF extractions or hand-crafted) for regression tests.

### NFR3: Maintainability
- Section header patterns must be centralized (e.g. a list or dict of regex patterns) and documented so new sections or variants can be added easily.

## Out of Scope (for this document)
- Parsing of images or handwritten content (OCR).
- Parsing of non-English resumes (language detection / translation).
- Automatic detection of candidate name/email/phone from structure only (that remains in AI extraction).
