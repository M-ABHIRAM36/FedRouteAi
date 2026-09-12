"""Restore full-HD bytes for the 5 JPEG figures (5.3-5.7) that Word downsampled
on save. python-docx copies blobs verbatim (no recompression), and preserves the
section numbering, updated LoF/LoT tables, citations and footer field results.
"""
import io, os, re
from docx import Document
from docx.oxml.ns import qn
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(HERE, "final_docx", "FEDROUTEAI DOC Final (citations + HD figures).docx")
PNGDIR = os.path.join(HERE, "final_hd_images", "png")
FIG_LIST = ["4.1","4.2","4.3","4.4","4.5","4.6","4.7","4.8","4.9","4.10","4.11",
            "5.1","5.2","5.3","5.4","5.5","5.6","5.7","6.1","6.2","6.3","7.1"]
png_by_num = {re.match(r"Fig_(\d+\.\d+)_", f).group(1): os.path.join(PNGDIR, f)
              for f in os.listdir(PNGDIR) if re.match(r"Fig_(\d+\.\d+)_.*\.png$", f)}

def hd_jpeg(path):
    im = Image.open(path).convert("RGB")
    bio = io.BytesIO(); im.save(bio, "JPEG", quality=95); return bio.getvalue()

doc = Document(FINAL)
restored = 0
for shape in doc.inline_shapes:
    try:
        blip = shape._inline.graphic.graphicData.pic.blipFill.blip
    except Exception:
        continue
    rId = blip.get(qn("r:embed"))
    if not rId:
        continue
    part = doc.part.related_parts[rId]
    m = re.search(r"image(\d+)\.(\w+)$", str(part.partname))
    if not m:
        continue
    N, ext = int(m.group(1)), m.group(2).lower()
    idx = N - 3
    if ext in ("jpeg", "jpg") and 0 <= idx < len(FIG_LIST):
        src = png_by_num.get(FIG_LIST[idx])
        if src:
            part._blob = hd_jpeg(src)
            restored += 1
doc.save(FINAL)
print(f"restored HD JPEG figures: {restored}")
