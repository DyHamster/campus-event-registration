"""将自备实验报告、UML 和源码打包为课程要求的 ZIP。"""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

CODE = Path(__file__).resolve().parents[1]
LAB = CODE.parent
SUBMISSION = "实验3_241870097_丁瀚铭"


def submission_files(report: Path) -> list[tuple[Path, str]]:
    """只选取提交所需材料。"""
    with report.open("rb") as stream:
        if not stream.read(5).startswith(b"%PDF-"):
            raise ValueError("请提供本人撰写并导出的实验报告 PDF。")

    files = [(report, "实验报告.pdf")]
    for filename in ("Makefile", "README.md", "requirements.txt"):
        files.append((CODE / filename, f"code/{filename}"))
    for folder, pattern in (
        ("campus_events", "*.py"),
        ("examples", "*.json"),
        ("tests", "*.py"),
        ("tools", "*.py"),
    ):
        for path in sorted((CODE / folder).glob(pattern)):
            files.append((path, f"code/{folder}/{path.name}"))

    uml = LAB / "UML"
    sources = sorted(uml.glob("*.puml"))
    if len(sources) != 4:
        raise ValueError("提交包需要四张 UML 图的 PlantUML 源文件。")
    for source in sources:
        files.append((source, f"UML/{source.name}"))
        image = source.with_suffix(".png")
        files.append((image, f"UML/{image.name}"))
    files.append((uml / "_style.iuml", "UML/_style.iuml"))

    for path, _ in files:
        if not path.is_file():
            raise FileNotFoundError(f"缺少提交材料：{path}")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="实验报告 PDF")
    parser.add_argument(
        "--directory", type=Path, default=LAB, help="ZIP 输出目录，默认为 Lab_3"
    )
    args = parser.parse_args()

    try:
        files = submission_files(args.report)
        output = args.directory / f"{SUBMISSION}.zip"
        with ZipFile(output, mode="x", compression=ZIP_DEFLATED) as archive:
            for source, relative in files:
                archive.write(source, f"{SUBMISSION}/{relative}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"打包失败：{error}\n")
    print(f"已生成：{output}")


if __name__ == "__main__":
    main()
