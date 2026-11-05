#!/usr/bin/env python3
"""Render local PlantUML sources into PNG and SVG. Requires Java and an official JAR."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import struct
import xml.etree.ElementTree as ET
import zlib


def verify_png(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path.name}")
    pos = 8
    compressed = []
    ended = False
    width = height = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError(f"PNG CRC mismatch: {path.name}")
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IDAT":
            compressed.append(payload)
        elif kind == b"IEND":
            ended = True
        pos += length + 12
    if not ended or pos != len(data) or not zlib.decompress(b"".join(compressed)):
        raise ValueError(f"Incomplete PNG: {path.name}")
    return data, width, height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    args = parser.parse_args()
    jar = args.jar.expanduser().resolve()
    java = shutil.which("java")
    if not java or not jar.is_file():
        parser.error("Java and an existing PlantUML JAR are required.")
    folder = Path(__file__).resolve().parents[1] / "UML"
    sources = sorted(folder.glob("*.puml"))
    if not sources:
        parser.error("No .puml sources found.")
    base = [java, "-Djava.awt.headless=true", "-DPLANTUML_LIMIT_SIZE=8192",
            "-jar", str(jar), "-charset", "UTF-8", "-failfast2"]
    subprocess.run(base + ["-checkonly"] + [str(p) for p in sources], check=True)
    for extension in ("png", "svg"):
        subprocess.run(base + ["-t" + extension] + [str(p) for p in sources], check=True)
    entries = []
    diagram_types = set()
    for source in sources:
        data, width, height = verify_png(source.with_suffix(".png"))
        svg = ET.parse(source.with_suffix(".svg")).getroot()
        labels = "".join(svg.itertext())
        if "Syntax Error?" in labels or "An error has occured" in labels:
            raise ValueError(f"Renderer error image: {source.name}")
        viewbox = [float(value) for value in svg.attrib["viewBox"].split()]
        if len(viewbox) != 4 or viewbox[2] <= 0 or viewbox[3] <= 0:
            raise ValueError(f"Invalid SVG canvas: {source.name}")
        type_match = re.search(r"title\s+UML\s+(类图|组件图|活动图|时序图|状态图)",
                               source.read_text(encoding="utf-8"))
        if not type_match:
            raise ValueError(f"UML type missing in title: {source.name}")
        diagram_types.add(type_match.group(1))
        entries.append({"source": source.name, "png": source.with_suffix(".png").name,
                        "svg": source.with_suffix(".svg").name, "width": width,
                        "height": height, "svg_viewbox": viewbox, "png_bytes": len(data),
                        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "png_sha256": hashlib.sha256(data).hexdigest()})
    result = {"renderer": "PlantUML", "jar": jar.name,
              "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
              "syntax_check": "passed", "png_crc_and_svg_check": "passed",
              "diagram_count": len(entries), "diagram_type_count": len(diagram_types),
              "diagram_types": sorted(diagram_types),
              "canvas_note": "PNG 与 SVG 的渲染边距可能略有不同，分别记录实际画布尺寸。",
              "files": entries}
    (folder / "渲染校验.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"diagrams": len(entries), "syntax": "passed",
                      "png_and_svg": "passed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

