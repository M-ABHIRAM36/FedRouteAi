"""Fix page numbering: make it continuous instead of the hard-coded per-section
restarts (start=1,6,3,10,...) that made the footer jump around.

Rule:
  * front-matter sections (fmt=lowerRoman) are left untouched (they are correct);
  * the FIRST decimal (body) section restarts at Arabic 1 -> Chapter 1 content = 1;
  * every later decimal section drops its 'start' attribute so numbering CONTINUES.
"""
from __future__ import annotations
import sys
from docx import Document
from docx.oxml.ns import qn

W_FMT = qn("w:fmt")
W_START = qn("w:start")


def is_roman(pgnum) -> bool:
    if pgnum is None:
        return False
    fmt = pgnum.get(W_FMT)
    return bool(fmt) and "oman" in fmt  # lowerRoman / upperRoman


def main(path: str):
    doc = Document(path)
    body = doc.element.body
    sectprs = list(body.iter(qn("w:sectPr")))
    roman_flags = [is_roman(sp.find(qn("w:pgNumType"))) for sp in sectprs]
    last_roman = max((i for i, f in enumerate(roman_flags) if f), default=-1)

    first_body = True
    changed = 0
    for i, sp in enumerate(sectprs):
        if i <= last_roman:
            continue  # front matter (title + roman pages) -> leave exactly as-is
        pg = sp.find(qn("w:pgNumType"))
        if pg is None:
            pg = sp.makeelement(qn("w:pgNumType"), {})
            sp.insert(0, pg)
        if first_body:
            pg.set(W_FMT, "decimal")
            pg.set(W_START, "1")
            first_body = False
        else:
            pg.set(W_FMT, "decimal")
            if W_START in pg.attrib:
                del pg.attrib[W_START]
        changed += 1
    doc.save(path)
    print(f"sections total: {len(sectprs)} | last roman section index: {last_roman} | body sections normalized: {changed}")
    print("first body section -> Arabic start=1 (Chapter 1 content); later body sections -> continuous")


if __name__ == "__main__":
    main(sys.argv[1])
