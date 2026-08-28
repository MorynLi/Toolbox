#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a deterministic directory tree, CSV file manifest, and scan summary."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

__version__ = "1.0.0"
GENERATED_NAMES = {"目录树.txt", "文件清单.csv", "扫描摘要.txt"}


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    parent_folder: str
    file_name: str
    extension: str
    size_bytes: int
    size_readable: str


def human_size(size: int) -> str:
    """Convert a byte count to a compact IEC-like human-readable value."""
    if size < 0:
        return "读取失败"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024 or unit == "PB":
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def matches_exclude(relative: Path, patterns: tuple[str, ...]) -> bool:
    """Return True when a relative path or any path component matches an exclude pattern."""
    posix = relative.as_posix()
    return any(
        fnmatch.fnmatch(posix, pattern)
        or fnmatch.fnmatch(relative.name, pattern)
        or any(fnmatch.fnmatch(part, pattern) for part in relative.parts)
        for pattern in patterns
    )


def iter_files(root: Path, patterns: tuple[str, ...], follow_symlinks: bool) -> tuple[list[Path], list[str]]:
    """Walk root deterministically while collecting non-fatal access errors."""
    files: list[Path] = []
    errors: list[str] = []

    def onerror(error: OSError) -> None:
        errors.append(f"{getattr(error, 'filename', '?')}: {error}")

    for current, dirnames, filenames in os.walk(root, topdown=True, onerror=onerror, followlinks=follow_symlinks):
        current_path = Path(current)
        dirnames[:] = sorted(
            [name for name in dirnames if not matches_exclude((current_path / name).relative_to(root), patterns)],
            key=str.casefold,
        )
        for name in sorted(filenames, key=str.casefold):
            path = current_path / name
            relative = path.relative_to(root)
            if not matches_exclude(relative, patterns):
                files.append(path)
    return files, errors


def scan(root: Path, patterns: tuple[str, ...], follow_symlinks: bool, ignored_exact: set[Path]) -> tuple[list[FileRecord], list[str]]:
    """Build file records without failing the whole scan on a single unreadable file."""
    paths, errors = iter_files(root, patterns, follow_symlinks)
    records: list[FileRecord] = []

    for path in paths:
        if path.resolve(strict=False) in ignored_exact:
            continue
        relative = path.relative_to(root)
        try:
            size = path.stat(follow_symlinks=follow_symlinks).st_size
        except OSError as error:
            size = -1
            errors.append(f"{relative.as_posix()}: {error}")
        records.append(
            FileRecord(
                relative_path=relative.as_posix(),
                parent_folder=relative.parent.as_posix(),
                file_name=path.name,
                extension=path.suffix.lower(),
                size_bytes=size,
                size_readable=human_size(size),
            )
        )

    records.sort(key=lambda record: record.relative_path.casefold())
    return records, errors


def write_tree(root: Path, output: Path, patterns: tuple[str, ...], ignored_exact: set[Path], follow_symlinks: bool) -> list[str]:
    """Write a readable tree and return non-fatal traversal errors."""
    errors: list[str] = []

    with output.open("w", encoding="utf-8-sig") as file:
        file.write(f"根目录：{root}\n\n")

        def recurse(folder: Path, prefix: str = "") -> None:
            try:
                items = list(folder.iterdir())
            except OSError as error:
                errors.append(f"{folder}: {error}")
                file.write(f"{prefix}└── [无法读取] {folder.name}\n")
                return

            visible: list[Path] = []
            for item in items:
                relative = item.relative_to(root)
                if item.resolve(strict=False) in ignored_exact or matches_exclude(relative, patterns):
                    continue
                visible.append(item)
            visible.sort(key=lambda path: (not path.is_dir(), path.name.casefold()))

            for index, item in enumerate(visible):
                last = index == len(visible) - 1
                branch = "└── " if last else "├── "
                child_prefix = prefix + ("    " if last else "│   ")

                if item.is_dir() and (follow_symlinks or not item.is_symlink()):
                    file.write(f"{prefix}{branch}[文件夹] {item.name}\n")
                    recurse(item, child_prefix)
                elif item.is_dir() and item.is_symlink():
                    file.write(f"{prefix}{branch}[目录链接] {item.name}\n")
                else:
                    try:
                        size = human_size(item.stat(follow_symlinks=follow_symlinks).st_size)
                    except OSError as error:
                        size = "读取失败"
                        errors.append(f"{relative.as_posix()}: {error}")
                    file.write(f"{prefix}{branch}{item.name} ({size})\n")

        recurse(root)
    return errors


def write_csv(records: list[FileRecord], output: Path) -> None:
    fieldnames = ["relative_path", "parent_folder", "file_name", "extension", "size_bytes", "size_readable"]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(record.__dict__ for record in records)


def write_summary(root: Path, records: list[FileRecord], errors: list[str], output: Path) -> None:
    extensions = Counter(record.extension or "[无扩展名]" for record in records)
    total_bytes = sum(record.size_bytes for record in records if record.size_bytes >= 0)
    folders = {record.parent_folder for record in records}

    with output.open("w", encoding="utf-8-sig") as file:
        file.write(f"根目录：{root}\n")
        file.write(f"文件总数：{len(records)}\n")
        file.write(f"包含文件的目录数：{len(folders)}\n")
        file.write(f"文件总大小：{human_size(total_bytes)}\n")
        file.write(f"读取错误数：{len(errors)}\n\n")
        file.write("按扩展名统计：\n")
        for extension, count in sorted(extensions.items(), key=lambda item: (-item[1], item[0])):
            file.write(f"{extension}: {count}\n")
        if errors:
            file.write("\n读取错误：\n")
            for error in errors:
                file.write(f"- {error}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="Directory to scan. Defaults to the script directory.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory. Defaults to the scan root.")
    parser.add_argument("--exclude", action="append", default=[], help="Glob pattern to exclude; may be repeated.")
    parser.add_argument("--follow-symlinks", action="store_true", help="Follow directory symbolic links (disabled by default).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_path = Path(__file__).resolve()
    root = (args.root or script_path.parent).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Scan root is not a directory: {root}")

    output_dir = (args.output_dir or root).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tree_out = output_dir / "目录树.txt"
    csv_out = output_dir / "文件清单.csv"
    summary_out = output_dir / "扫描摘要.txt"

    ignored_exact = {script_path, tree_out.resolve(strict=False), csv_out.resolve(strict=False), summary_out.resolve(strict=False)}
    patterns = tuple(args.exclude)

    records, scan_errors = scan(root, patterns, args.follow_symlinks, ignored_exact)
    tree_errors = write_tree(root, tree_out, patterns, ignored_exact, args.follow_symlinks)
    errors = scan_errors + tree_errors
    write_csv(records, csv_out)
    write_summary(root, records, errors, summary_out)

    print(tree_out)
    print(csv_out)
    print(summary_out)


if __name__ == "__main__":
    main()
