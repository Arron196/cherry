from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


ROOT = Path(__file__).resolve().parent
INPUT_DOC = ROOT / "论文——模板编辑_按规范排版_配图版_v5_内联公式修复.docx"
OUTPUT_DOC = ROOT / "论文——模板编辑_按规范排版_配图版_v6_目录修复_草稿.docx"


def insert_paragraph_after(paragraph: Paragraph) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def main() -> None:
    shutil.copy2(INPUT_DOC, OUTPUT_DOC)
    doc = Document(OUTPUT_DOC)

    toc_heading = None
    for para in doc.paragraphs:
        text = para.text.strip().replace("\n", " ")
        if text in {"目  录", "目录", "目 录"}:
            toc_heading = para
            break

    if toc_heading is None:
        raise RuntimeError("未找到目录标题。")

    toc_heading.text = "目  录"

    # 清理目录标题后到下一节之间的空白与旧占位
    cur = toc_heading._p.getnext()
    while cur is not None:
        para = Paragraph(cur, toc_heading._parent)
        ppr = cur.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        has_sectpr = ppr is not None and ppr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr') is not None
        text = para.text.strip().replace("\n", " ")
        if has_sectpr:
            break
        nxt = cur.getnext()
        para._element.getparent().remove(para._element)
        cur = nxt

    placeholder = insert_paragraph_after(toc_heading)
    placeholder.text = "[[TOC]]"

    doc.save(OUTPUT_DOC)
    print(OUTPUT_DOC)


if __name__ == "__main__":
    main()
