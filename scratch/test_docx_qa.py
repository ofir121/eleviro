import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from app.utils.parsers import DEFAULT_PIPELINE_CONFIG
extractor = DEFAULT_PIPELINE_CONFIG.extractors['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
with open('Ofir Shliefer CV Master 2026.docx', 'rb') as f:
    text = extractor(f.read())
    for line in text.split('\n'):
        if "Validated" in line or "Coordinated" in line:
            print(repr(line))
