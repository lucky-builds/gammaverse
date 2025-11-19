#!/usr/bin/env python3
"""
Remove the Gamma watermark annotation from a PDF without touching other content.

Usage:
    PDF_FILE=/absolute/path/file.pdf python3 remove_gamma_logo_pdf.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, NameObject, NumberObject
    from pypdf._page import ContentStream
except ImportError as exc:
    print("Error: pypdf is required to run this script.", file=sys.stderr)
    raise

ENV_VAR = "PDF_FILE"
GAMMA_HOST = "gamma.app"
GAMMA_IMG_WIDTH = 575
GAMMA_IMG_HEIGHT = 137
BLANK_PIXEL = b"\x00\x00\x00"


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def should_remove_annotation(annot_obj) -> bool:
    action = annot_obj.get("/A")
    if not action:
        return False
    uri = action.get("/URI")
    if not isinstance(uri, str):
        return False
    return GAMMA_HOST in uri.lower()


def find_gamma_xobjects(page) -> dict:
    resources = page.get("/Resources")
    if not resources:
        return {}
    xobjects = resources.get("/XObject") or {}

    targets = {}
    for name, obj in xobjects.items():
        img = obj.get_object()
        if (
            img.get("/Subtype") == "/Image"
            and img.get("/Width") == GAMMA_IMG_WIDTH
            and img.get("/Height") == GAMMA_IMG_HEIGHT
        ):
            targets[name] = img
    return targets


def scrub_gamma_images(targets: dict) -> int:
    scrubbed = 0
    for name, img in targets.items():
        img._data = BLANK_PIXEL
        img[NameObject("/Width")] = NumberObject(1)
        img[NameObject("/Height")] = NumberObject(1)
        img[NameObject("/BitsPerComponent")] = NumberObject(8)
        img[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
        img[NameObject("/Length")] = NumberObject(len(BLANK_PIXEL))
        for key in ("/Filter", "/DecodeParms", "/SMask", "/Mask"):
            if key in img:
                del img[NameObject(key)]
        scrubbed += 1
    return scrubbed


def strip_draw_commands(page, reader, targets: dict) -> int:
    if not targets:
        return 0
    contents = page.get("/Contents")
    if not contents:
        return 0

    content = ContentStream(contents, reader)
    ops = content.operations
    removed = 0
    target_names = set(targets.keys())

    i = 0
    while i < len(ops):
        operands, operator = ops[i]
        if (
            operator == b"Do"
            and operands
            and operands[0] in target_names
        ):
            start = i
            depth = 0
            j = i - 1
            while j >= 0:
                op = ops[j][1]
                if op == b"Q":
                    depth += 1
                elif op == b"q":
                    if depth == 0:
                        start = j
                        break
                    depth -= 1
                j -= 1

            end = i
            depth = 0
            k = i + 1
            while k < len(ops):
                op = ops[k][1]
                end = k
                if op == b"q":
                    depth += 1
                elif op == b"Q":
                    if depth == 0:
                        break
                    depth -= 1
                k += 1

            del ops[start : end + 1]
            removed += 1
            continue
        i += 1

    if removed:
        content.operations = ops
        page[NameObject("/Contents")] = content

    return removed


def process_pdf(path: Path) -> int:
    reader = PdfReader(path)
    writer = PdfWriter()
    annotations_removed = 0
    images_scrubbed = 0

    for page in reader.pages:
        gamma_targets = find_gamma_xobjects(page)
        annots = page.get("/Annots")
        if annots:
            new_annots = []
            for annot in annots:
                annot_obj = annot.get_object()
                if should_remove_annotation(annot_obj):
                    annotations_removed += 1
                    continue
                new_annots.append(annot)

            if len(new_annots) != len(annots):
                if new_annots:
                    page[NameObject("/Annots")] = ArrayObject(new_annots)
                else:
                    page.pop("/Annots", None)

        images_scrubbed += scrub_gamma_images(gamma_targets)
        strip_draw_commands(page, reader, gamma_targets)
        writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(reader.metadata)

    total_removed = annotations_removed + images_scrubbed
    if total_removed == 0:
        return 0

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with open(tmp_path, "wb") as fh:
            writer.write(fh)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return total_removed


def main() -> None:
    pdf_path = os.getenv(ENV_VAR)
    if not pdf_path:
        fail(f"{ENV_VAR} environment variable is not set.")

    path = Path(pdf_path).expanduser()
    if not path.exists():
        fail(f"PDF file not found: {path}")

    removed = process_pdf(path)
    if removed == 0:
        print("No Gamma watermark elements found; no changes made.")
    else:
        print(f"Removed {removed} Gamma watermark element(s).")


if __name__ == "__main__":
    main()

