#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a deterministic AI conversation handoff package from a JSON spec."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.2.0"
SCHEMA_VERSION = "0.2"
HANDOFF_TARGET = Path("HANDOFF.md")
RESERVED_TARGETS = {"HANDOFF.md", "manifest.json", "QA.md"}


@dataclass(frozen=True)
class Item:
    source: Path
    target: Path
    label: str
    role: str
    required: bool
    source_name: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def safe_target(value: str) -> Path:
    target = Path(value.replace("\\", "/"))
    if target.is_absolute() or not target.parts:
        raise ValueError(f"Target must be a non-empty relative path: {value!r}")
    if any(part in {"", ".", ".."} for part in target.parts):
        raise ValueError(f"Unsafe target path: {value!r}")
    if target.as_posix() in RESERVED_TARGETS:
        raise ValueError(f"Target is reserved by conversation_pack: {value!r}")
    return target


def resolve_source(value: str, spec_dir: Path) -> Path:
    source = Path(value).expanduser()
    if source.is_absolute():
        return source.resolve(strict=False)
    return (spec_dir / source).resolve(strict=False)


def parse_asset(raw: dict, spec_dir: Path) -> Item:
    source_value = raw.get("source")
    target_value = raw.get("target")
    if not isinstance(source_value, str) or not source_value.strip():
        raise ValueError("Each asset requires a non-empty string 'source'.")
    if not isinstance(target_value, str) or not target_value.strip():
        raise ValueError("Each asset requires a non-empty string 'target'.")

    source = resolve_source(source_value, spec_dir)
    target = safe_target(target_value)
    label = str(raw.get("label") or source.name)
    role = str(raw.get("role") or "asset")
    required = bool(raw.get("required", True))
    return Item(
        source=source,
        target=target,
        label=label,
        role=role,
        required=required,
        source_name=source.name,
    )


def load_spec(path: Path) -> tuple[dict, Path, list[Item]]:
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON spec: {error}") from error

    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version: {spec.get('schema_version')!r}; expected {SCHEMA_VERSION!r}."
        )

    pack_name = spec.get("pack_name")
    if not isinstance(pack_name, str) or not pack_name.strip():
        raise ValueError("spec.pack_name must be a non-empty string.")
    if any(char in pack_name for char in '<>:"/\\|?*'):
        raise ValueError("spec.pack_name contains characters unsafe for common filesystems.")

    handoff_value = spec.get("handoff")
    if not isinstance(handoff_value, str) or not handoff_value.strip():
        raise ValueError("spec.handoff must be a non-empty string path to HANDOFF.md source content.")

    spec_dir = path.parent.resolve()
    handoff_source = resolve_source(handoff_value, spec_dir)

    raw_assets = spec.get("assets", [])
    if not isinstance(raw_assets, list):
        raise ValueError("spec.assets must be a list.")
    assets: list[Item] = []
    for raw in raw_assets:
        if not isinstance(raw, dict):
            raise ValueError("Each assets entry must be an object.")
        assets.append(parse_asset(raw, spec_dir))

    targets = [item.target.as_posix() for item in assets]
    duplicates = sorted({target for target in targets if targets.count(target) > 1})
    if duplicates:
        raise ValueError(f"Duplicate target paths: {duplicates}")

    return spec, handoff_source, assets


def build_pack(
    spec_path: Path,
    output_dir: Path | None,
    force: bool,
    make_zip: bool,
) -> tuple[Path, Path | None]:
    spec_path = spec_path.expanduser().resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    spec, handoff_source, assets = load_spec(spec_path)
    pack_name = spec["pack_name"].strip()

    if output_dir is None:
        pack_root = spec_path.parent / "_conversation_pack" / pack_name
    else:
        pack_root = output_dir.expanduser().resolve()

    zip_path = pack_root.parent / f"{pack_root.name}.zip" if make_zip else None

    if pack_root.exists():
        if not force:
            raise FileExistsError(f"Output directory already exists: {pack_root}. Use --force to rebuild.")
        shutil.rmtree(pack_root)
    if zip_path and zip_path.exists():
        if not force:
            raise FileExistsError(f"ZIP already exists: {zip_path}. Use --force to rebuild.")
        zip_path.unlink()

    if not handoff_source.is_file():
        raise FileNotFoundError(f"HANDOFF source file is missing: {handoff_source.name}")

    missing_required = [item for item in assets if item.required and not item.source.is_file()]
    missing_optional = [item for item in assets if not item.required and not item.source.is_file()]
    if missing_required:
        names = ", ".join(item.label for item in missing_required)
        raise FileNotFoundError(f"Required approved assets are missing: {names}")

    pack_root.mkdir(parents=True, exist_ok=False)

    manifest_items: list[dict] = []
    total_size = 0
    copied_count = 0

    handoff_destination = pack_root / HANDOFF_TARGET
    shutil.copy2(handoff_source, handoff_destination)
    handoff_size = handoff_destination.stat().st_size
    total_size += handoff_size
    copied_count += 1
    manifest_items.append(
        {
            "target": HANDOFF_TARGET.as_posix(),
            "source_name": handoff_source.name,
            "label": "Conversation handoff",
            "role": "entrypoint",
            "required": True,
            "size_bytes": handoff_size,
            "sha256": sha256_file(handoff_destination),
        }
    )

    for item in assets:
        if not item.source.is_file():
            continue
        destination = pack_root / item.target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, destination)
        size = destination.stat().st_size
        total_size += size
        copied_count += 1
        manifest_items.append(
            {
                "target": item.target.as_posix(),
                "source_name": item.source_name,
                "label": item.label,
                "role": item.role,
                "required": item.required,
                "size_bytes": size,
                "sha256": sha256_file(destination),
            }
        )

    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "pack_name": pack_name,
        "created_at": created_at,
        "file_count": copied_count,
        "total_size_bytes": total_size,
        "items": manifest_items,
        "missing_optional": [
            {
                "source_name": item.source_name,
                "target": item.target.as_posix(),
                "label": item.label,
                "role": item.role,
            }
            for item in missing_optional
        ],
    }
    (pack_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    qa_lines = [
        "# Conversation Pack QA",
        "",
        f"- pack_name: `{pack_name}`",
        f"- schema_version: `{SCHEMA_VERSION}`",
        f"- tool_version: `{__version__}`",
        f"- created_at: `{created_at}`",
        f"- HANDOFF.md: **OK**",
        f"- copied files: **{copied_count}**",
        f"- total size: **{total_size} bytes**",
        "- missing required approved assets: **0**",
        f"- missing optional assets: **{len(missing_optional)}**",
        "",
    ]
    if missing_optional:
        qa_lines.extend(["## Missing optional assets", ""])
        for item in missing_optional:
            qa_lines.append(f"- `{item.target.as_posix()}` — {item.label} ({item.role})")
        qa_lines.append("")
    qa_lines.extend(
        [
            "## Integrity",
            "",
            "Every copied payload file is listed in `manifest.json` with SHA-256 and byte size.",
            "The builder does not modify source files and does not include local absolute source paths in the manifest.",
            "Semantic correctness of `HANDOFF.md` and asset selection must be approved before this builder is run.",
            "",
        ]
    )
    (pack_root / "QA.md").write_text("\n".join(qa_lines), encoding="utf-8")

    if make_zip and zip_path is not None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(pack_root.rglob("*"), key=lambda value: value.as_posix().casefold()):
                if path.is_file():
                    archive.write(path, arcname=Path(pack_root.name) / path.relative_to(pack_root))

    return pack_root, zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to conversation pack spec.json")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Final pack directory. Default: <spec_dir>/_conversation_pack/<pack_name>",
    )
    parser.add_argument("--zip", action="store_true", help="Also create a ZIP next to the pack directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing output directory/ZIP.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pack_root, zip_path = build_pack(args.spec, args.output_dir, args.force, args.zip)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(pack_root)
    if zip_path is not None:
        print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
