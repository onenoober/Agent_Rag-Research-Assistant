# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from src.libs.vector_store.chroma_store import ChromaStore
from src.core.settings import load_settings
import re

settings = load_settings()
store = ChromaStore(settings=settings, collection_name='test_academic_paper')

collection = store.client.get_collection('test_academic_paper')
results = collection.get(include=['documents'])

print("=" * 60)
print("STORED CONTENT ANALYSIS")
print("=" * 60)

# Merge all content
all_text = '\n'.join(results['documents'])

# Find formulas
print("\n[FORMULA DETECTION]")
formulas = [
    (r'h\s*=\s*f\s*\(\s*x\s*\)', 'h = f(x)'),
    (r'p\s*\(\s*y\s*=\s*1\s*\|\s*x\s*\)\s*=\s*σ', 'p(y=1|x) = sigma'),
    (r'L\s*=\s*-\s*\(\s*1/N\s*\)', 'L = -(1/N)'),
]

for pattern, name in formulas:
    matches = re.findall(pattern, all_text, re.IGNORECASE)
    if matches:
        print(f"  OK - {name}: found {len(matches)} occurrences")
    else:
        print(f"  MISSING - {name}")

# Formula markers (1), (2), (3)
formula_markers = re.findall(r'\((\d+)\)', all_text)
print(f"  Formula markers: {formula_markers}")

# Find tables
print("\n[TABLE DETECTION]")
table_patterns = [
    (r'TABLE\s+I', 'TABLE I'),
    (r'Logistic\s+Regression', 'Logistic Regression'),
    (r'MLP\s+Classifier', 'MLP Classifier'),
    (r'Neural\s+Encoder', 'Neural Encoder'),
    (r'Accuracy', 'Accuracy column'),
    (r'F1-score', 'F1-score column'),
]

for pattern, name in table_patterns:
    if re.search(pattern, all_text, re.IGNORECASE):
        print(f"  OK - {name}")
    else:
        print(f"  MISSING - {name}")

print("\n[TABLE DATA]")
table_section = re.search(r'TABLE I.*?Accuracy.*?F1-score', all_text, re.DOTALL)
if table_section:
    print(table_section.group()[:500])

print("\n" + "=" * 60)
print(f"Total chunks: {len(results['documents'])}")
print(f"Total chars: {len(all_text)}")
print("=" * 60)
