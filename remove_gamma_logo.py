#!/usr/bin/env python3
"""
Utility to strip the "Made with GAMMA" watermark from a PPTX file.

Usage:
    PPTX_FILE=/absolute/path/to/deck.pptx python3 remove_gamma_logo.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Set, Tuple
import xml.etree.ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

PIC_TAG = f"{{{NS['p']}}}pic"
ENV_VAR = "PPTX_FILE"

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_archive(path: Path) -> Tuple[Dict[str, zipfile.ZipInfo], Dict[str, bytes]]:
    infos: Dict[str, zipfile.ZipInfo] = {}
    contents: Dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zin:
        for info in zin.infolist():
            infos[info.filename] = info
            contents[info.filename] = zin.read(info.filename)
    return infos, contents


def strip_gamma_from_layout(
    layout_bytes: bytes,
    rel_bytes: bytes | None,
) -> Tuple[bytes, bytes | None, bool]:
    changed = False
    rel_tree = None
    gamma_hlink_ids: Set[str] = set()

    if rel_bytes:
        rel_tree = ET.fromstring(rel_bytes)
        for rel in list(rel_tree):
            rel_type = rel.get("Type", "")
            target = rel.get("Target", "")
            if (
                "hyperlink" in rel_type
                and "gamma.app" in target.lower()
                and rel.get("Id")
            ):
                gamma_hlink_ids.add(rel.get("Id"))
                rel_tree.remove(rel)
                changed = True

    if not gamma_hlink_ids:
        return layout_bytes, rel_bytes, changed

    layout_tree = ET.fromstring(layout_bytes)
    embed_ids_to_remove: Set[str] = set()

    def should_remove(pic) -> bool:
        for hlink in pic.findall(".//a:hlinkClick", NS):
            rid = hlink.get(f"{{{NS['r']}}}id")
            if rid in gamma_hlink_ids:
                return True
        return False

    def walk(parent):
        nonlocal changed
        for child in list(parent):
            walk(child)
        for child in list(parent):
            if child.tag == PIC_TAG and should_remove(child):
                for blip in child.findall(".//a:blip", NS):
                    rid = blip.get(f"{{{NS['r']}}}embed")
                    if rid:
                        embed_ids_to_remove.add(rid)
                parent.remove(child)
                changed = True

    walk(layout_tree)

    if not changed:
        return layout_bytes, rel_bytes, False

    if rel_tree is not None and embed_ids_to_remove:
        for rel in list(rel_tree):
            if rel.get("Id") in embed_ids_to_remove:
                rel_tree.remove(rel)

    new_layout = ET.tostring(layout_tree, encoding="utf-8", xml_declaration=True)
    new_rels = (
        ET.tostring(rel_tree, encoding="utf-8", xml_declaration=True)
        if rel_tree is not None
        else rel_bytes
    )
    return new_layout, new_rels, True


def write_archive(
    path: Path,
    infos: Dict[str, zipfile.ZipInfo],
    contents: Dict[str, bytes],
) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w") as zout:
            for name, info in infos.items():
                zout.writestr(info, contents[name])
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def main() -> None:
    pptx_path = os.getenv(ENV_VAR)
    if not pptx_path:
        fail(f"{ENV_VAR} environment variable is not set.")

    path = Path(pptx_path).expanduser()
    if not path.exists():
        fail(f"PPTX file not found: {path}")

    infos, contents = load_archive(path)
    layout_names = [
        name
        for name in contents
        if name.startswith("ppt/slideLayouts/") and name.endswith(".xml")
    ]

    total_removed = 0

    for layout_name in layout_names:
        rel_name = f"ppt/slideLayouts/_rels/{Path(layout_name).name}.rels"
        layout_bytes = contents[layout_name]
        rel_bytes = contents.get(rel_name)

        new_layout, new_rels, changed = strip_gamma_from_layout(
            layout_bytes, rel_bytes
        )

        if changed:
            contents[layout_name] = new_layout
            if new_rels is not None:
                contents[rel_name] = new_rels
            elif rel_name in contents:
                del contents[rel_name]
                del infos[rel_name]
            total_removed += 1

    if total_removed == 0:
        print("No Gamma watermark found; no changes made.")
        return

    write_archive(path, infos, contents)
    print(f"Removed Gamma watermark from {total_removed} layout(s).")


if __name__ == "__main__":
    main()

