from app.utils.parsers import extract_contact_from_text

text = """Ofir Shliefer
Ofir Shliefer Gaithersburg, MD · 973-800-9119 · ofir.shliefer@gmail.com · gmail.com"""

c = extract_contact_from_text(text)
print("Location:", repr(c.location))
print("Phones:", c.phones)
print("Emails:", c.emails)
print("Other URLs:", c.other_urls)
