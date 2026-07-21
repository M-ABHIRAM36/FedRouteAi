from docx import Document

doc = Document('c:/Users/DELL/Desktop/Major Project/fedrouteai/docs/conference-template-a4.docx')
print(f"Total paragraphs: {len(doc.paragraphs)}")
for i, p in enumerate(doc.paragraphs[:20]):
    print(f"{i}: {p.text.strip()}")
