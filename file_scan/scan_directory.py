#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a compact, AI-oriented index for a directory tree."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

__version__ = "2.0.0"
SCHEMA_VERSION = "2.0"
DEFAULT_OUTPUT_DIRNAME = "_file_scan"
DEFAULT_MAX_DEPTH = 4

FOLDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "cache",
    "dist",
    "build",
}

DEPENDENCY_DIR_NAMES = {
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
}

GENERATED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "cache",
    "dist",
    "build",
}

SOURCE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".f", ".f90", ".f95", ".for", ".f03", ".f08",
    ".go", ".rs", ".java", ".cs", ".swift", ".kt", ".kts",
    ".r", ".jl", ".lua", ".php", ".rb", ".scala",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".sql", ".html", ".htm", ".css", ".scss", ".sass", ".less",
}

DOCUMENT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst", ".tex",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".rtf",
}

DATA_EXTENSIONS = {
    ".csv", ".tsv", ".xlsx", ".xls", ".ods",
    ".parquet", ".feather", ".jsonl", ".ndjson",
    ".nc", ".netcdf", ".h5", ".hdf5", ".mat",
    ".npy", ".npz", ".dat", ".data",
    ".grib", ".grb", ".grib2", ".grb2",
    ".shp", ".shx", ".dbf", ".geojson",
    ".sqlite", ".sqlite3", ".db",
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".xml", ".lock", ".properties",
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff",
    ".webp", ".svg", ".eps",
}

ARCHIVE_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz",
    ".tbz", ".tbz2", ".txz",
}

BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".pyd", ".node", ".lib",
    ".obj", ".o", ".a", ".class", ".jar", ".war", ".bin",
}

CONFIG_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "environment.yml",
    "environment.yaml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "vite.config.js",
    "vite.config.ts",
    "webpack.config.js",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "makefile",
    "cmakelists.txt",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
}

IMPORTANT_NAMES = CONFIG_NAMES | {
    "readme.md",
    "readme.txt",
    "license",
    "license.md",
    "changelog.md",
    "main.py",
    "app.py",
    "index.html",
}


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    parent_folder: str
    file_name: str
    extension: str
    size_bytes: int
    size_readable: str
    modified_time: str
    depth: int
    category: str


@dataclass
class DirectoryStats:
    files: int = 0
    bytes: int = 0


def now_local() -> datetime:
    return datetime.now().astimezone()


def human_size(size: int) -> str:
    """Convert a byte count to a compact binary-unit display."""
    if size < 0:
        return "read failed"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024 or unit == "PB":
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def path_stat(path: Path, follow_symlinks: bool):
    """Use APIs compatible with Python 3.9+."""
    return path.stat() if follow_symlinks else path.lstat()


def matches_exclude(relative: Path, patterns: tuple[str, ...]) -> bool:
    """Return True when a relative path or any component matches a glob."""
    posix = relative.as_posix()
    return any(
        fnmatch.fnmatch(posix, pattern)
        or fnmatch.fnmatch(relative.name, pattern)
        or any(fnmatch.fnmatch(part, pattern) for part in relative.parts)
        for pattern in patterns
    )


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def should_ignore_path(
    path: Path,
    ignored_subtrees: tuple[Path, ...],
    ignored_exact: set[Path],
) -> bool:
    resolved = path.resolve(strict=False)
    if resolved in ignored_exact:
        return True
    return any(is_within(resolved, subtree) for subtree in ignored_subtrees)


def classify_file(relative: Path) -> str:
    """Assign a broad, domain-neutral category for AI filtering."""
    parts = {part.casefold() for part in relative.parts[:-1]}
    name = relative.name.casefold()
    suffix = relative.suffix.casefold()

    if parts & DEPENDENCY_DIR_NAMES:
        return "dependency"
    if parts & GENERATED_DIR_NAMES or suffix in {".pyc", ".pyo"}:
        return "generated"
    if name in CONFIG_NAMES or suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix in SOURCE_EXTENSIONS:
        return "source"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    if suffix in DATA_EXTENSIONS:
        return "data"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in ARCHIVE_EXTENSIONS:
        return "archive"
    if suffix in BINARY_EXTENSIONS:
        return "binary"
    return "other"


def iter_files(
    root: Path,
    patterns: tuple[str, ...],
    follow_symlinks: bool,
    ignored_subtrees: tuple[Path, ...],
    ignored_exact: set[Path],
) -> tuple[list[Path], list[str]]:
    """Walk root deterministically while collecting non-fatal errors."""
    files: list[Path] = []
    errors: list[str] = []

    def onerror(error: OSError) -> None:
        errors.append(f"{getattr(error, 'filename', '?')}: {error}")

    for current, dirnames, filenames in os.walk(
        root,
        topdown=True,
        onerror=onerror,
        followlinks=follow_symlinks,
    ):
        current_path = Path(current)

        visible_dirs: list[str] = []
        for name in dirnames:
            path = current_path / name
            relative = path.relative_to(root)
            if should_ignore_path(path, ignored_subtrees, ignored_exact):
                continue
            if matches_exclude(relative, patterns):
                continue
            visible_dirs.append(name)
        dirnames[:] = sorted(visible_dirs, key=str.casefold)

        for name in sorted(filenames, key=str.casefold):
            path = current_path / name
            relative = path.relative_to(root)
            if should_ignore_path(path, ignored_subtrees, ignored_exact):
                continue
            if not matches_exclude(relative, patterns):
                files.append(path)

    return files, errors


def scan(
    root: Path,
    patterns: tuple[str, ...],
    follow_symlinks: bool,
    ignored_subtrees: tuple[Path, ...],
    ignored_exact: set[Path],
) -> tuple[list[FileRecord], list[str]]:
    """Build file records without failing on one unreadable file."""
    paths, errors = iter_files(
        root,
        patterns,
        follow_symlinks,
        ignored_subtrees,
        ignored_exact,
    )
    records: list[FileRecord] = []

    for path in paths:
        relative = path.relative_to(root)
        try:
            stat = path_stat(path, follow_symlinks)
            size = stat.st_size
            modified_time = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
        except OSError as error:
            size = -1
            modified_time = ""
            errors.append(f"{relative.as_posix()}: {error}")

        records.append(
            FileRecord(
                relative_path=relative.as_posix(),
                parent_folder=relative.parent.as_posix(),
                file_name=path.name,
                extension=path.suffix.casefold(),
                size_bytes=size,
                size_readable=human_size(size),
                modified_time=modified_time,
                depth=len(relative.parent.parts),
                category=classify_file(relative),
            )
        )

    records.sort(key=lambda record: record.relative_path.casefold())
    return records, errors


def build_directory_stats(records: list[FileRecord]) -> dict[str, DirectoryStats]:
    stats: dict[str, DirectoryStats] = defaultdict(DirectoryStats)
    for record in records:
        relative = Path(record.relative_path)
        parents = relative.parts[:-1]
        for index in range(1, len(parents) + 1):
            key = Path(*parents[:index]).as_posix()
            stats[key].files += 1
            if record.size_bytes >= 0:
                stats[key].bytes += record.size_bytes
    return dict(stats)


def write_tree(
    root: Path,
    output: Path,
    patterns: tuple[str, ...],
    ignored_subtrees: tuple[Path, ...],
    ignored_exact: set[Path],
    follow_symlinks: bool,
    records: list[FileRecord],
    max_depth: int,
    full_tree: bool,
) -> list[str]:
    """Write a compact tree, folding low-value or overly deep directories."""
    errors: list[str] = []
    dir_stats = build_directory_stats(records)

    def folder_stats(relative: Path) -> DirectoryStats:
        return dir_stats.get(relative.as_posix(), DirectoryStats())

    with output.open("w", encoding="utf-8-sig") as file:
        file.write(f"Root: {root}\n")
        if full_tree:
            file.write("Tree mode: full\n\n")
        else:
            file.write(f"Tree mode: compact; max directory depth={max_depth}\n")
            file.write("Folded directories: " + ", ".join(sorted(FOLDED_DIR_NAMES)) + "\n\n")

        def recurse(folder: Path, prefix: str = "", directory_depth: int = 0) -> None:
            try:
                items = list(folder.iterdir())
            except OSError as error:
                errors.append(f"{folder}: {error}")
                file.write(f"{prefix}└── [unreadable] {folder.name}\n")
                return

            visible: list[Path] = []
            for item in items:
                relative = item.relative_to(root)
                if should_ignore_path(item, ignored_subtrees, ignored_exact):
                    continue
                if matches_exclude(relative, patterns):
                    continue
                visible.append(item)

            def sort_key(path: Path):
                try:
                    directory = path.is_dir()
                except OSError:
                    directory = False
                return (not directory, path.name.casefold())

            visible.sort(key=sort_key)

            for index, item in enumerate(visible):
                last = index == len(visible) - 1
                branch = "└── " if last else "├── "
                child_prefix = prefix + ("    " if last else "│   ")
                relative = item.relative_to(root)

                try:
                    is_dir = item.is_dir()
                    is_link = item.is_symlink()
                except OSError as error:
                    errors.append(f"{relative.as_posix()}: {error}")
                    file.write(f"{prefix}{branch}[unreadable] {item.name}\n")
                    continue

                if is_dir and is_link and not follow_symlinks:
                    file.write(f"{prefix}{branch}[dir symlink] {item.name}\n")
                    continue

                if is_dir:
                    stats = folder_stats(relative)
                    child_depth = directory_depth + 1
                    fold_reason = None
                    if not full_tree and item.name.casefold() in FOLDED_DIR_NAMES:
                        fold_reason = "low-value directory"
                    elif not full_tree and child_depth > max_depth:
                        fold_reason = "max depth"

                    if fold_reason:
                        file.write(
                            f"{prefix}{branch}[dir] {item.name}/ "
                            f"[folded: {fold_reason}; {stats.files} files; {human_size(stats.bytes)}]\n"
                        )
                    else:
                        file.write(f"{prefix}{branch}[dir] {item.name}/\n")
                        recurse(item, child_prefix, child_depth)
                    continue

                try:
                    size = human_size(path_stat(item, follow_symlinks).st_size)
                except OSError as error:
                    size = "read failed"
                    errors.append(f"{relative.as_posix()}: {error}")
                file.write(f"{prefix}{branch}{item.name} ({size})\n")

        recurse(root)

    return errors


def write_csv(records: list[FileRecord], output: Path) -> None:
    fieldnames = [
        "relative_path",
        "parent_folder",
        "file_name",
        "extension",
        "size_bytes",
        "size_readable",
        "modified_time",
        "depth",
        "category",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|")


def important_entries(records: list[FileRecord], limit: int = 30) -> list[FileRecord]:
    candidates = [
        record
        for record in records
        if record.file_name.casefold() in IMPORTANT_NAMES
        or record.file_name.casefold().startswith(("readme", "requirements"))
    ]
    return sorted(candidates, key=lambda record: (record.depth, record.relative_path.casefold()))[:limit]


def write_summary(
    root: Path,
    records: list[FileRecord],
    errors: list[str],
    output: Path,
    started_at: datetime,
    finished_at: datetime,
    max_depth: int,
    full_tree: bool,
) -> None:
    extensions = Counter(record.extension or "[no extension]" for record in records)
    categories = Counter(record.category for record in records)
    total_bytes = sum(record.size_bytes for record in records if record.size_bytes >= 0)
    folders = {record.parent_folder for record in records}

    top_level: dict[str, DirectoryStats] = defaultdict(DirectoryStats)
    for record in records:
        relative = Path(record.relative_path)
        key = relative.parts[0] if len(relative.parts) > 1 else "[root files]"
        top_level[key].files += 1
        if record.size_bytes >= 0:
            top_level[key].bytes += record.size_bytes

    largest = sorted(
        (record for record in records if record.size_bytes >= 0),
        key=lambda record: (-record.size_bytes, record.relative_path.casefold()),
    )[:20]

    with output.open("w", encoding="utf-8-sig") as file:
        file.write("# File Scan Summary\n\n")
        file.write("AI-oriented entry point for this directory scan. Read this file first; use `tree.txt` for structure and `files.csv` for exact file-level lookup.\n\n")

        file.write("## Scan metadata\n\n")
        file.write(f"- Root: `{root}`\n")
        file.write(f"- Started: `{started_at.isoformat(timespec='seconds')}`\n")
        file.write(f"- Finished: `{finished_at.isoformat(timespec='seconds')}`\n")
        file.write(f"- Tool version: `{__version__}`\n")
        file.write(f"- Files: **{len(records)}**\n")
        file.write(f"- Directories containing files: **{len(folders)}**\n")
        file.write(f"- Total file size: **{human_size(total_bytes)}**\n")
        file.write(f"- Read/traversal errors: **{len(errors)}**\n")
        file.write(f"- Tree mode: **{'full' if full_tree else f'compact, max depth {max_depth}'}**\n\n")

        file.write("## Recommended AI reading order\n\n")
        file.write("1. `summary.md` — overall structure, dominant file types, key entry files.\n")
        file.write("2. `tree.txt` — compact directory layout; dependency/generated folders are folded by default.\n")
        file.write("3. `files.csv` — authoritative file-level index for filtering by path, type, size, time, depth, or category.\n")
        file.write("4. `manifest.json` — machine-readable scan metadata and schema information.\n\n")

        file.write("## Top-level distribution\n\n")
        file.write("| top-level item | files | size |\n")
        file.write("|---|---:|---:|\n")
        for key, stats in sorted(top_level.items(), key=lambda item: (-item[1].files, item[0].casefold())):
            file.write(f"| {markdown_escape(key)} | {stats.files} | {human_size(stats.bytes)} |\n")
        file.write("\n")

        file.write("## Categories\n\n")
        file.write("| category | files |\n")
        file.write("|---|---:|\n")
        for category, count in sorted(categories.items(), key=lambda item: (-item[1], item[0])):
            file.write(f"| {category} | {count} |\n")
        file.write("\n")

        file.write("## Extensions\n\n")
        file.write("| extension | files |\n")
        file.write("|---|---:|\n")
        for extension, count in sorted(extensions.items(), key=lambda item: (-item[1], item[0]))[:50]:
            file.write(f"| {markdown_escape(extension)} | {count} |\n")
        if len(extensions) > 50:
            file.write(f"\nTop 50 shown; {len(extensions)} distinct extension groups exist in `files.csv`.\n")
        file.write("\n")

        entries = important_entries(records)
        file.write("## Important entry files\n\n")
        if entries:
            for record in entries:
                file.write(f"- `{record.relative_path}` — {record.category}, {record.size_readable}\n")
        else:
            file.write("No common entry/configuration filenames were detected.\n")
        file.write("\n")

        file.write("## Largest files\n\n")
        file.write("| relative path | size | category |\n")
        file.write("|---|---:|---|\n")
        for record in largest:
            file.write(
                f"| `{markdown_escape(record.relative_path)}` | {record.size_readable} | {record.category} |\n"
            )
        file.write("\n")

        if errors:
            file.write("## Errors\n\n")
            for error in errors:
                file.write(f"- {error}\n")
        else:
            file.write("## Errors\n\nNo read or traversal errors were recorded.\n")


def write_manifest(
    root: Path,
    output_dir: Path,
    records: list[FileRecord],
    errors: list[str],
    output: Path,
    started_at: datetime,
    finished_at: datetime,
    patterns: tuple[str, ...],
    follow_symlinks: bool,
    max_depth: int,
    full_tree: bool,
) -> None:
    total_bytes = sum(record.size_bytes for record in records if record.size_bytes >= 0)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "tool": "file_scan",
        "tool_version": __version__,
        "root": str(root),
        "output_dir": str(output_dir),
        "scan_started_at": started_at.isoformat(timespec="seconds"),
        "scan_finished_at": finished_at.isoformat(timespec="seconds"),
        "file_count": len(records),
        "directories_containing_files": len({record.parent_folder for record in records}),
        "total_size_bytes": total_bytes,
        "error_count": len(errors),
        "follow_symlinks": follow_symlinks,
        "exclude_patterns": list(patterns),
        "tree": {
            "mode": "full" if full_tree else "compact",
            "max_depth": None if full_tree else max_depth,
            "folded_directory_names": [] if full_tree else sorted(FOLDED_DIR_NAMES),
        },
        "outputs": {
            "summary": "summary.md",
            "tree": "tree.txt",
            "files": "files.csv",
            "manifest": "manifest.json",
        },
        "files_csv_schema": [
            "relative_path",
            "parent_folder",
            "file_name",
            "extension",
            "size_bytes",
            "size_readable",
            "modified_time",
            "depth",
            "category",
        ],
    }

    with output.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="Directory to scan. Defaults to the script directory.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Exact output directory. Defaults to <root>/{DEFAULT_OUTPUT_DIRNAME}.",
    )
    parser.add_argument("--exclude", action="append", default=[], help="Glob pattern to exclude; may be repeated.")
    parser.add_argument("--follow-symlinks", action="store_true", help="Follow directory symbolic links (disabled by default).")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"Maximum directory depth expanded in compact tree mode (default: {DEFAULT_MAX_DEPTH}).",
    )
    parser.add_argument("--full-tree", action="store_true", help="Disable tree folding and depth limiting.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def dedupe_errors(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def main() -> None:
    args = parse_args()
    if args.max_depth < 0:
        raise ValueError("--max-depth must be >= 0")

    script_path = Path(__file__).resolve()
    root = (args.root or script_path.parent).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Scan root is not a directory: {root}")

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else root / DEFAULT_OUTPUT_DIRNAME
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_out = output_dir / "summary.md"
    tree_out = output_dir / "tree.txt"
    csv_out = output_dir / "files.csv"
    manifest_out = output_dir / "manifest.json"

    generated_outputs = {
        summary_out.resolve(strict=False),
        tree_out.resolve(strict=False),
        csv_out.resolve(strict=False),
        manifest_out.resolve(strict=False),
    }

    # If the output directory is a child of the scan root, exclude the entire
    # result subtree so repeated scans never index their own generated files.
    ignored_subtrees: tuple[Path, ...]
    if output_dir != root and is_within(output_dir, root):
        ignored_subtrees = (output_dir.resolve(strict=False),)
        ignored_exact: set[Path] = set()
    else:
        ignored_subtrees = ()
        ignored_exact = generated_outputs

    patterns = tuple(args.exclude)
    started_at = now_local()

    records, scan_errors = scan(
        root,
        patterns,
        args.follow_symlinks,
        ignored_subtrees,
        ignored_exact,
    )
    tree_errors = write_tree(
        root,
        tree_out,
        patterns,
        ignored_subtrees,
        ignored_exact,
        args.follow_symlinks,
        records,
        args.max_depth,
        args.full_tree,
    )
    errors = dedupe_errors(scan_errors + tree_errors)
    finished_at = now_local()

    write_csv(records, csv_out)
    write_summary(
        root,
        records,
        errors,
        summary_out,
        started_at,
        finished_at,
        args.max_depth,
        args.full_tree,
    )
    write_manifest(
        root,
        output_dir,
        records,
        errors,
        manifest_out,
        started_at,
        finished_at,
        patterns,
        args.follow_symlinks,
        args.max_depth,
        args.full_tree,
    )

    print(summary_out)
    print(tree_out)
    print(csv_out)
    print(manifest_out)


if __name__ == "__main__":
    main()
