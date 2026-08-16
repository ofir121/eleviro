---
name: eleviro-navigator
description: |
  Map of the Eleviro codebase (FastAPI resume/cover-letter AI assistant) — where routes, parsing,
  AI prompts, formatting, and DOCX generation live, plus the request flow that ties them together.

  Use when: orienting in this repo, finding where to make a change (parsing bug, new AI prompt,
  new resume section, DOCX export tweak, new API route), swapping the OpenAI model, or figuring
  out which test file covers a given module.
user-invocable: true
---

# Eleviro Navigator

Eleviro is a FastAPI app that takes a resume (PDF/DOCX/text) + job description, parses the resume
into sections, asks OpenAI to suggest edits, and lets the user export a tailored DOCX.

## Run & setup

- `make run` — `uvicorn main:app --reload` (app at http://127.0.0.1:8000)
- `make test` — `pytest` (the `tests/` suite only)
- Config comes from `.env` (loaded via `python-dotenv` in `ai_service.py`):
  - `OPENAI_API_KEY` — required for real AI calls; without it the OpenAI `client` is `None`
  - `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_BASE_URL` — optional LLM tracing
    (the OpenAI client is Langfuse-wrapped)
- Model names live at the top of `app/services/ai_service.py`: `reasoning_model`,
  `writing_model`, `TESTING_MODEL` — change models there.

## Entry point

- `main.py` — FastAPI app setup, mounts `app/static`, renders `app/templates`, includes
  `app/routers/job_router.py`. Routes: `/`, `/documentation`, `/health`.

## Request flow (upload → export)

All API routes live in `app/routers/job_router.py`, prefixed `/api`:

1. **Upload/parse** — `POST /api/process-job` (handler `process_job`) accepts the resume file +
   job description, calls `app/utils/parsers.py::run_pipeline()` to extract raw text
   (PDF/DOCX/plain, with optional OCR fallback for scanned PDFs), then splits it into sections.
2. **AI analysis** — `app/services/ai_service.py` calls OpenAI (all async, via the shared
   `get_completion()` wrapper) for: job summary (`summarize_job`), company research
   (`research_company`), candidate info extraction (`extract_candidate_info`), resume section
   extraction (`parse_resume_sections_with_ai`), rewrite suggestions (`suggest_resume_changes`),
   bold-keyword suggestions (`suggest_bold_changes`/`bold_keywords`), cover letters
   (`generate_cover_letter`), outreach messages (`generate_outreach`), and recruiter lookup
   (`find_recruiters` — uses DuckDuckGo search via `ddgs`, not OpenAI alone).
3. **Apply edits** — `POST /api/apply-changes` (handler `apply_changes`) merges accepted
   `ResumeSuggestion`s (and bolding) back into the resume text via `apply_suggestions_to_text`.
4. **Format** — `app/utils/formatters.py::build_markdown_resume()` turns parsed sections +
   contact info into clean markdown (section-specific rules for skills/experience/education/
   certifications).
5. **Export** — `POST /api/download` (handler `download_document`) calls
   `app/utils/generators.py::create_docx()` to render the final markdown as a styled `.docx`
   (Calibri, centered header, hyperlinks, bold keywords) returned as a `StreamingResponse`.

Other routes: `POST /api/generate-section` (handler `generate_section`, regenerates one section),
`POST /api/generate-outreach` (handler `generate_outreach_endpoint`, cold outreach message).

## Key modules

| Module | Responsibility |
|---|---|
| `app/routers/job_router.py` | All `/api/*` endpoints; suggestion merge/apply logic (`apply_suggestions_to_text`, `merge_bolding_into_rewrites`) |
| `app/services/ai_service.py` | Every OpenAI prompt/call + model config; most functions take `is_testing_mode` for cheap canned responses |
| `app/utils/parsers.py` | File extraction (PDF/DOCX/plain), OCR fallback, section splitting/regex, contact extraction (`ExtractedContact`), `ParsedResume`, `run_pipeline()` |
| `app/utils/formatters.py` | Parsed sections → markdown, per-section formatting rules |
| `app/utils/generators.py` | Markdown → DOCX rendering (`create_docx`, hyperlinks, bold/italic runs) |
| `app/config/section_patterns.py` | `CANONICAL_SECTION_ORDER` + `SECTION_HEADER_VARIANTS` regex config for section headers — edit here to support a new section name, no parser code changes needed |
| `app/models/suggestions.py` | Pydantic models: `ResumeSuggestion`, `ApplyChangesRequest`, etc. |
| `app/templates/index.html` + `app/static/js/main.js` | Single-page frontend; `main.js` (~900 lines) holds all client logic, CSS in `app/static/css/` |

## Tests

- `tests/` is the real suite (`make test` / `pytest`): `test_parsers.py`, `test_formatters.py`,
  `test_ai_service.py`, `test_router.py`, `test_models.py`, `test_basic.py`,
  `test_performance_mock.py`. `conftest.py` provides a `client` fixture (FastAPI `TestClient`).
  Fixtures live in `tests/fixtures/sample_resumes/`.
- Root-level `test_clean.py`, `test_contact.py`, `test_docx.py`, `test_router.py`,
  `test_summary.py` and everything in `scratch/` are ad-hoc scratch scripts for manual poking —
  NOT part of the suite, not run by `make test`.

## Docs worth reading before parser changes

- `docs/PARSER_REQUIREMENTS.md`, `docs/PARSER_DESIGN.md`,
  `docs/PARSER_BUGS_AND_IMPLEMENTATION_PLAN.md`
- `README.md` has a "Parser extensibility" section on adding new section patterns or file formats.

## Extending the parser (from README)

- **New section** (e.g. "Patents"): add a key to `SECTION_HEADER_VARIANTS` and append the
  canonical name to `CANONICAL_SECTION_ORDER` in `app/config/section_patterns.py`. No changes
  needed in `parsers.py` — patterns are compiled at import via `build_section_patterns()`.
- **New file format** (e.g. RTF): implement `extract_rtf(content: bytes) -> str` in `parsers.py`,
  register it in `DEFAULT_PIPELINE_CONFIG.extractors`, and accept the extension in the upload
  route.

## Gotchas

- OCR is **optional**: `parsers.py` sets `_OCR_AVAILABLE` based on whether `pymupdf` +
  `pytesseract` import successfully; scanned-PDF support silently degrades without them.
- Most AI-service functions take `is_testing_mode: bool` to skip real OpenAI calls (used by the
  app's "Testing Mode" toggle and by `test_performance_mock.py`).
- `uploads/` accumulates uploaded/modified resume files at runtime — not source, ignore when
  navigating.
- There are two `test_router.py` files: `tests/test_router.py` (real suite) and root-level
  `test_router.py` (scratch) — make sure you're editing the right one.
