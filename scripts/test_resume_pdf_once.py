#!/usr/bin/env python3
"""
One-off script to test resume PDF parsing and contact extraction.
Uses a local PDF path; NOT part of the test suite (file may contain sensitive data and is gitignored).
Run from project root: python scripts/test_resume_pdf_once.py [path/to/resume.pdf]
Requires a path argument; no default file is used to avoid relying on personal documents.
"""
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.parsers import (
    _extract_pdf_text_with_ocr_fallback,
    extract_contact_from_text,
    is_plausible_phone,
)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_resume_pdf_once.py <path/to/resume.pdf>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    content = path.read_bytes()
    raw_text = _extract_pdf_text_with_ocr_fallback(content)
    contact = extract_contact_from_text(raw_text)

    print("Contact extraction from PDF:")
    print("  Phones:", contact.phones)
    print("  Emails:", contact.emails[:3])
    print("  Location:", contact.location)

    # Bug fix: no date range should appear as phone
    bad_phones = [p for p in contact.phones if "July" in p or "Present" in p or not is_plausible_phone(p)]
    if bad_phones:
        print("  FAIL: Invalid phones (date range or not plausible):", bad_phones)
        sys.exit(1)
    print("  OK: No date range in phones; all phones are plausible.")

    if contact.phones:
        print("  Resolved phone for contact bar would be:", contact.phones[0])
    else:
        print("  No phone found in PDF (contact bar would show no phone).")


if __name__ == "__main__":
    main()
