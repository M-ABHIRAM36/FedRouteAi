import json
import os

with open(r'C:\Users\DELL\.gemini\antigravity-ide\brain\95596ac6-6534-4c1c-ae69-ceac18e89a83\scratch\verified_references.json', 'r', encoding='utf-8') as f:
    refs = json.load(f)

bibtex_entries = [r['bibtex'].strip() for r in refs if 'bibtex' in r]
with open('c:/Users/DELL/Desktop/Major Project/fedrouteai/docs/paper/latex/references.bib', 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(bibtex_entries))
print('Created references.bib')
