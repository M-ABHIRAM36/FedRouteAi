"""Embed the HD figure renders into the report, IN PLACE, on a copy.

Base = the citations version (keeps clickable [n] citations + figure/table refs).
For each of the 22 figure images (word/media/image3..image24) we replace the
underlying image bytes with the matching HD render and set a uniform, proper
display width (aspect preserved, no distortion). Logos and everything else are
untouched. Original files are never modified.
"""
from __future__ import annotations
import io
import os
import re
import shutil

from docx import Document
from docx.shared import Emu
from docx.oxml.ns import qn
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "with_citations", "FEDROUTEAI DOC Final v1.00 (citations).docx")
PNGDIR = os.path.join(HERE, "final_hd_images", "png")
OUTDIR = os.path.join(HERE, "final_docx")
OUT = os.path.join(OUTDIR, "FEDROUTEAI DOC Final (citations + HD figures).docx")

# media image number N (image{N}) -> figure, for N = 3..24
FIG_LIST = ["4.1","4.2","4.3","4.4","4.5","4.6","4.7","4.8","4.9","4.10","4.11",
            "5.1","5.2","5.3","5.4","5.5","5.6","5.7","6.1","6.2","6.3","7.1"]

# map figure number -> rendered PNG path
png_by_num = {}
for fn in os.listdir(PNGDIR):
    m = re.match(r"Fig_(\d+\.\d+)_.*\.png$", fn)
    if m:
        png_by_num[m.group(1)] = os.path.join(PNGDIR, fn)


def png_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def jpeg_bytes(path, quality=92):
    im = Image.open(path).convert("RGB")
    bio = io.BytesIO()
    im.save(bio, format="JPEG", quality=quality)
    return bio.getvalue()


def aspect(path):
    im = Image.open(path)
    return im.height / im.width


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    shutil.copyfile(BASE, OUT)
    doc = Document(OUT)
    sec = doc.sections[0]
    content_w = sec.page_width - sec.left_margin - sec.right_margin
    width = int(content_w * 0.98)

    replaced = 0
    skipped = []
    for shape in doc.inline_shapes:
        try:
            blip = shape._inline.graphic.graphicData.pic.blipFill.blip
        except Exception:
            continue
        rId = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
        if not rId:
            continue
        part = doc.part.related_parts[rId]
        name = str(part.partname)             # e.g. /word/media/image16.jpeg
        mm = re.search(r"image(\d+)\.(\w+)$", name)
        if not mm:
            continue
        N = int(mm.group(1)); ext = mm.group(2).lower()
        idx = N - 3
        if idx < 0 or idx >= len(FIG_LIST):
            skipped.append(name)             # logo etc.
            continue
        num = FIG_LIST[idx]
        src = png_by_num.get(num)
        if not src:
            skipped.append(f"{name} (no png for {num})")
            continue
        data = jpeg_bytes(src) if ext in ("jpeg", "jpg") else png_bytes(src)
        part._blob = data                     # swap image bytes, keep part identity
        shape.width = Emu(width)              # uniform, centered, aspect-correct
        shape.height = Emu(int(width * aspect(src)))
        replaced += 1

    doc.save(OUT)
    print(f"saved: {OUT}")
    print(f"figures replaced with HD renders: {replaced}/22")
    print(f"display width: {round(width/360000,2)} cm (uniform, centered)")
    print(f"non-figure images left untouched: {len(skipped)} -> {skipped}")


if __name__ == "__main__":
    main()
