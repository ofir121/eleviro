import re
from app.utils.parsers import ExtractedContact

line = "Ofir Shliefer Gaithersburg, MD · 973-800-9119 · ofir.shliefer@gmail.com · U.S. Permanent Residence Accomplished data professional with over 7 years of experience"

candidate_name = "Ofir Shliefer"
contact = ExtractedContact(
    phones=["973-800-9119"],
    emails=["ofir.shliefer@gmail.com"],
    location="Gaithersburg, MD",
    linkedin_urls=[], portfolio_urls=[], other_urls=[], security_clearance=None
)

start_idx = 0
for e in (contact.emails or []):
    idx = line.find(e)
    if idx != -1: start_idx = max(start_idx, idx + len(e))
for p in (contact.phones or []):
    idx = line.find(p)
    if idx != -1: start_idx = max(start_idx, idx + len(p))
for u in (contact.linkedin_urls or []) + (contact.portfolio_urls or []) + (contact.other_urls or []):
    idx = line.find(u)
    if idx != -1: start_idx = max(start_idx, idx + len(u))
    
clean_summary = line[start_idx:]

if candidate_name: clean_summary = clean_summary.replace(candidate_name, "")
if contact.location: clean_summary = clean_summary.replace(contact.location, "")
if contact.security_clearance: clean_summary = clean_summary.replace(contact.security_clearance, "")

clean_summary = re.sub(r"^[^a-zA-Z0-9]+", "", clean_summary.strip())
print("CLEANED:", clean_summary)
