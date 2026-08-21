import os
import re

bib_path = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper\final_compilable_project\references.bib"

with open(bib_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace unicode dashes (en-dash, em-dash) with standard LaTeX dashes (--)
text_fixed = text.replace("–", "--").replace("—", "---")

# Replace non-breaking spaces or weird quotes
text_fixed = text_fixed.replace("’", "'").replace("“", "``").replace("”", "''")

if text_fixed != text:
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(text_fixed)
    print("Fixed unicode characters (en-dashes, smart quotes) in references.bib")
else:
    print("references.bib is already clean.")
