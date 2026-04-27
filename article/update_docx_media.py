from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def replace_docx_media(source_docx: Path, output_docx: Path, media_dir: Path) -> list[str]:
    replacements = {
        file.name: file
        for file in media_dir.glob("image*.png")
    }
    replaced: list[str] = []

    with zipfile.ZipFile(source_docx, "r") as src, zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            target_name = info.filename
            media_name = Path(target_name).name

            if target_name.startswith("word/media/") and media_name in replacements:
                dst.writestr(target_name, replacements[media_name].read_bytes())
                replaced.append(media_name)
                continue

            dst.writestr(info, src.read(target_name))

    return sorted(replaced)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: update_docx_media.py <source_docx> <output_docx> <media_dir>", file=sys.stderr)
        return 2

    source_docx = Path(sys.argv[1]).resolve()
    output_docx = Path(sys.argv[2]).resolve()
    media_dir = Path(sys.argv[3]).resolve()

    if not source_docx.exists():
        print(f"source docx not found: {source_docx}", file=sys.stderr)
        return 1
    if not media_dir.exists():
        print(f"media directory not found: {media_dir}", file=sys.stderr)
        return 1

    replaced = replace_docx_media(source_docx, output_docx, media_dir)
    print(f"replaced {len(replaced)} media files into {output_docx}")
    for name in replaced:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
