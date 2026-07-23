import os
import re

base_dir = r"C:\Users\DELL\Desktop\Major Project\fedrouteai\docs\paper\final_compilable_project"

# 1. Parse bib keys
bib_path = os.path.join(base_dir, "references.bib")
with open(bib_path, "r", encoding="utf-8") as f:
    bib_text = f.read()

bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib_text))
print(f"Total keys in references.bib: {len(bib_keys)}")

# 2. Parse all \cite{...} across all tex files
cited_keys = set()
tex_files = []
for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".tex"):
            tex_files.append(os.path.join(root, file))

missing_found = False
for tex in sorted(tex_files):
    rel = os.path.relpath(tex, base_dir)
    with open(tex, "r", encoding="utf-8") as f:
        content = f.read()
    cites = re.findall(r"\\cite\{([^}]+)\}", content)
    for c in cites:
        for k in c.split(","):
            k = k.strip()
            if k:
                cited_keys.add(k)
                if k not in bib_keys:
                    print(f"❌ ERROR: Cited key '{k}' in {rel} NOT FOUND in references.bib!")
                    missing_found = True

print(f"\nTotal unique cited keys in manuscript: {len(cited_keys)}")
print("Cited keys:", sorted(list(cited_keys)))

if not missing_found:
    print("\n✓ SUCCESS: All cited keys exist in references.bib!")

# 3. Check for uncited bib keys
uncited = bib_keys - cited_keys
if uncited:
    print(f"\nNote: {len(uncited)} keys in references.bib are unused in manuscript:")
    print(sorted(list(uncited)))
