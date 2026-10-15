#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publication profiles: fonts, sizes, label grammar, width classes, multi-format export."""

from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.text import Text

ENGINE_VERSION = "2.0.0"
PROFILE_DIR = Path(__file__).with_name("profiles")
FONT_DIR_ENV = "ACADEMIC_PLOT_FONT_DIR"
MM_PER_INCH = 25.4
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def load_profile(name_or_path: str | Path) -> dict[str, Any]:
    path = Path(name_or_path)
    if not path.suffix:
        path = PROFILE_DIR / f"{name_or_path}.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _register_font_dir(font_dir: str | Path | None) -> None:
    for folder in [font_dir, os.environ.get(FONT_DIR_ENV)]:
        if not folder:
            continue
        for path in sorted(Path(folder).glob("*")):
            if path.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                try:
                    font_manager.fontManager.addfont(str(path))
                except (RuntimeError, OSError):
                    # C:\Windows\Fonts holds files FreeType cannot open; a missing profile font still raises below.
                    continue


def _font_file(name: str, *, style: str = "normal", weight: int = 400) -> str | None:
    for font in font_manager.fontManager.ttflist:
        if font.name == name and font.style == style and font.weight == weight:
            return font.fname
    return None


def setup_fonts(profile: dict[str, Any], *, draft: bool = False, font_dir: str | Path | None = None) -> dict[str, str]:
    """Configure rcParams from a profile.

    final (default): the profile fonts must exist, otherwise raise; nothing silently falls back.
    draft: metric-compatible substitutes (Liberation Serif ~ Times New Roman, CJK glyphs are
    1 em wide in both SimSun and Noto Serif CJK), so geometry matches the final render.
    """
    _register_font_dir(font_dir)
    fonts = profile["fonts"]
    latin, cjk = fonts["latin"], fonts["cjk"]
    if draft:
        # Prefer the real fonts when present; substitute only what is missing.
        if _font_file(latin) is None:
            latin = fonts["draft_latin"]
        if cjk and _font_file(cjk) is None:
            cjk = fonts["draft_cjk"]
    needed = {"latin": (latin, "normal", 400), "latin_italic": (latin, "italic", 400), "latin_bold": (latin, "normal", 700)}
    if cjk:
        needed["cjk"] = (cjk, "normal", 400)

    resolved: dict[str, str] = {}
    missing = []
    for role, (name, style, weight) in needed.items():
        path = _font_file(name, style=style, weight=weight)
        if path is None:
            missing.append(f"{name} ({style}, {weight})")
        else:
            resolved[role] = path
    if missing:
        hint = "" if draft else f" Pass --font-dir / set {FONT_DIR_ENV} to a folder with the font files, or use --draft."
        raise RuntimeError(f"Missing fonts for profile '{profile['name']}': {', '.join(missing)}.{hint}")

    rcParams.update(
        {
            "font.family": [latin] + ([cjk] if cjk else []),
            "mathtext.fontset": "custom",
            "mathtext.rm": latin,
            "mathtext.it": f"{latin}:italic",
            "mathtext.bf": f"{latin}:bold",
            "axes.unicode_minus": True,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
        }
    )
    return resolved


def style_defaults(profile: dict[str, Any]) -> dict[str, Any]:
    """Map profile sizes onto the style keys used by the plotting scripts."""
    size = profile["font_size_pt"]
    line = profile["line_width_pt"]
    return {
        "tick_fontsize": size["tick"],
        "axis_label_fontsize": size["label"],
        "legend_fontsize": size["legend"],
        "station_fontsize": size["panel_label"],
        "panel_label_fontsize": size["panel_label"],
        "annotation_fontsize": size["annotation"],
        "spine_width": line["spine"],
        "tick_width": line["tick"],
        "tick_length": profile["tick_length_pt"],
        "observed_line_width": line["reference"],
        "reference_line_width": line["reference"],
        "simulated_line_width": line["simulation"],
        "simulation_line_width": line["simulation"],
        "contour_line_width": line["contour"],
        "coast_line_width": line["coast"],
    }


def label_text(spec: str | dict[str, Any], profile: dict[str, Any] | None) -> str:
    """Compose an axis/colorbar label from {quantity, symbol, unit}; plain strings pass through.

    zh (GB 3102 style): "有效波高 $H_s$/m", compound units wrapped: "风速 $V$/(m/s)".
    en: "$H_s$ (m)"; without a symbol: "Significant wave height (m)".
    """
    if isinstance(spec, str) or profile is None:
        return spec if isinstance(spec, str) else str(spec.get("text", ""))
    lang = profile["lang"]
    quantity = spec.get("quantity", "")
    if isinstance(quantity, dict):
        quantity = quantity.get(lang, "")
    symbol = f"${spec['symbol']}$" if spec.get("symbol") else ""
    unit = str(spec.get("unit", "")).strip()

    if lang == "zh":
        head = " ".join(part for part in (quantity, symbol) if part)
        if not unit:
            return head
        if re.search(r"[/\s·]", unit):
            unit = f"({unit})"
        return f"{head}/{unit}"
    head = symbol or quantity
    return f"{head} ({unit})" if unit else head


CJK = re.compile(r"[　-〿一-鿿＀-￯]")
PT_TO_MM = MM_PER_INCH / 72.0


def _runs(text: str) -> list[str]:
    """Split text into CJK-plain runs and Latin/mathtext runs.

    Mathtext has no font fallback, so a run that contains CJK must not contain '$', and a
    math run must not contain CJK. Latin plain text can live in either kind.
    """
    if "$" not in text or not CJK.search(text):
        return [text]
    runs: list[str] = []
    for piece in re.split(r"(\$[^$]*\$)", text):
        if not piece:
            continue
        kind = "cjk" if CJK.search(piece) else "latin"
        if runs and kind == "latin" and not CJK.search(runs[-1]):
            runs[-1] += piece
        else:
            runs.append(piece)
    return runs


def draw_label(
    fig: plt.Figure,
    text: str,
    x_mm: float,
    y_mm: float,
    *,
    fontsize: float,
    rotation: int = 0,
) -> list[Any]:
    """Draw a label centred on (x_mm, y_mm) in figure millimetres, CJK+math safe.

    Horizontal: (x, y) is the centre of the text line. rotation=90: x is the baseline,
    y the centre along the text. All runs share one baseline.
    """
    if not text:
        return []
    canvas_w = fig.get_figwidth() * MM_PER_INCH
    canvas_h = fig.get_figheight() * MM_PER_INCH
    renderer = fig.canvas.get_renderer()
    runs = _runs(text)
    widths = []
    for run in runs:
        probe = fig.text(0, 0, run, fontsize=fontsize)
        widths.append(probe.get_window_extent(renderer).width / fig.dpi * MM_PER_INCH)
        probe.remove()
    start = -sum(widths) / 2.0
    baseline_shift = 0.33 * fontsize * PT_TO_MM
    artists = []
    group = object()
    for run, width in zip(runs, widths):
        if rotation == 90:
            pos = (x_mm, y_mm + start)
        else:
            pos = (x_mm + start, y_mm - baseline_shift)
        artists.append(
            fig.text(
                pos[0] / canvas_w,
                pos[1] / canvas_h,
                run,
                fontsize=fontsize,
                rotation=rotation,
                rotation_mode="anchor",
                ha="left",
                va="baseline",
            )
        )
        artists[-1]._label_group = id(group)
        start += width
    return artists


def axes_box_mm(fig: plt.Figure, ax: Any) -> tuple[float, float, float, float]:
    """Return (left, bottom, width, height) of an axes in figure millimetres."""
    box = ax.get_position()
    canvas_w = fig.get_figwidth() * MM_PER_INCH
    canvas_h = fig.get_figheight() * MM_PER_INCH
    return box.x0 * canvas_w, box.y0 * canvas_h, box.width * canvas_w, box.height * canvas_h


def text_overlaps(fig: plt.Figure, *, gap_mm: float = 1.0) -> list[str]:
    """Report visible texts closer than gap_mm to each other, or leaving the canvas (figure mm)."""
    tol_mm = 0.0
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    scale = MM_PER_INCH / fig.dpi
    canvas_w = fig.get_figwidth() * MM_PER_INCH
    canvas_h = fig.get_figheight() * MM_PER_INCH
    # x/y tick labels of one axes meet at the corner by matplotlib's own layout; not a defect.
    tick_owner = {
        id(label): id(ax)
        for ax in fig.axes
        for label in ax.get_xticklabels() + ax.get_yticklabels()
    }
    boxes = []
    seen: set[int] = set()
    for text in fig.findobj(Text):
        if id(text) in seen:
            continue
        seen.add(id(text))
        if not text.get_visible() or not str(text.get_text()).strip():
            continue
        if text.axes is not None and not text.axes.get_visible():
            continue
        box = text.get_window_extent(renderer)
        if id(text) in tick_owner:
            group = ("ticks", tick_owner[id(text)])
        else:
            group = getattr(text, "_label_group", id(text))
        boxes.append((str(text.get_text()), box.x0 * scale, box.y0 * scale, box.x1 * scale, box.y1 * scale, group))

    problems = []
    for name, x0, y0, x1, y1, _ in boxes:
        if x0 < -tol_mm or y0 < -tol_mm or x1 > canvas_w + tol_mm or y1 > canvas_h + tol_mm:
            problems.append(f"outside canvas: {name!r}")
    for i, (a, ax0, ay0, ax1, ay1, ga) in enumerate(boxes):
        for b, bx0, by0, bx1, by1, gb in boxes[i + 1:]:
            if ga == gb:
                continue
            if min(ax1, bx1) - max(ax0, bx0) > -gap_mm and min(ay1, by1) - max(ay0, by0) > -gap_mm:
                problems.append(f"too close (< {gap_mm} mm): {a!r} / {b!r}")
    return problems


def panel_letter(index: int, profile: dict[str, Any] | None) -> str:
    fmt = (profile or {}).get("panel_label", {}).get("format", "({letter})")
    return fmt.format(letter=LETTERS[index])


def width_geometry(geometry: dict[str, Any], rows: int, cols: int, profile: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve {"width": "full", "panel_aspect": 0.4} into explicit panel/gap/margin millimetres.

    Margins and gaps are profile constants (they depend on font size), so every figure in the
    same width class has identical text geometry; only the panel box follows the width.
    """
    if "width" not in geometry:
        return geometry
    if profile is None:
        raise ValueError("layout.geometry.width requires a profile.")
    width = geometry["width"]
    canvas_w = float(profile["widths_mm"][width]) if isinstance(width, str) else float(width)

    defaults = profile["geometry_mm"]
    gap = [float(v) for v in geometry.get("gap_mm", defaults["gap"])]
    margin = dict(defaults["margin"])
    margin.update(geometry.get("margin_mm", {}))

    panel_w = (canvas_w - margin["left"] - margin["right"] - (cols - 1) * gap[0]) / cols
    if "panel_height_mm" in geometry:
        panel_h = float(geometry["panel_height_mm"])
    else:
        panel_h = panel_w * float(geometry.get("panel_aspect", 0.62))
    if panel_w <= 0 or panel_h <= 0:
        raise ValueError(f"Width class '{width}' leaves no room for {cols} panel columns.")

    resolved = {key: value for key, value in geometry.items() if key not in {"width", "panel_aspect", "panel_height_mm"}}
    resolved.update({"panel_size_mm": [panel_w, panel_h], "gap_mm": gap, "margin_mm": margin})
    return resolved


def export_figure(
    fig: plt.Figure,
    output: Path,
    *,
    profile: dict[str, Any] | None,
    fixed_geometry: bool,
    draft: bool = False,
    qc: dict[str, Any] | None = None,
    export: dict[str, Any] | None = None,
) -> list[Path]:
    """Save every format next to `output` (profile formats, or spec `export` override).

    A legacy '.svg' output with no profile saves SVG only. Each file carries the engine version
    and profile in its metadata so any figure can be traced back to how it was made.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    if profile is None:
        formats, dpi = [output.suffix.lstrip(".") or "svg"], 300
    else:
        formats = list(profile["export"]["formats"])
        dpi = int(profile["export"]["png_dpi"])
    if export:
        formats = list(export.get("formats", formats))
        dpi = int(export.get("png_dpi", dpi))
    stem = output.with_suffix("")
    if draft:
        fig.text(0.995, 0.005, "DRAFT", ha="right", va="bottom", fontsize=6, color="#B00000", alpha=0.7)

    qc_mode = str((qc or {}).get("text", "error" if profile is not None else "off")).lower()
    if qc_mode != "off":
        problems = text_overlaps(fig, gap_mm=float((qc or {}).get("min_gap_mm", 1.0)))
        if problems:
            message = "Text layout QC failed:\n  " + "\n  ".join(problems)
            if qc_mode == "error":
                plt.close(fig)
                raise ValueError(message)
            warnings.warn(message, RuntimeWarning, stacklevel=2)

    kwargs: dict[str, Any] = {"facecolor": "white"}
    if not fixed_geometry:
        kwargs.update(bbox_inches="tight", pad_inches=0.03)
    written = []
    stamp = f"academic_plot {ENGINE_VERSION}; profile={(profile or {}).get('name', 'legacy')}; fonts={'draft' if draft else 'final'}"
    for fmt in formats:
        path = stem.with_suffix(f".{fmt}")
        meta = {"Creator": stamp}
        if fmt in {"png", "svg"}:
            meta["Description"] = stamp
        # dpi also sets the resolution of rasterized layers (filled contours) inside PDF/SVG.
        fig.savefig(path, format=fmt, dpi=dpi, metadata=meta, **kwargs)
        written.append(path)
    plt.close(fig)
    return written


def write_caption_snippet(
    output: Path,
    caption: dict[str, Any] | None,
    *,
    width_mm: float,
    profile: dict[str, Any] | None,
    export: dict[str, Any] | None = None,
) -> Path | None:
    """Write the figure title as text next to the artwork; it never goes inside the image.

    <stem>.tex: LaTeX block (\\bicaption for the thesis, \\caption for journals), width in mm.
    <stem>.caption.txt: the same title for pasting into a Word caption (题注).
    """
    if not caption or profile is None:
        return None
    stem = output.with_suffix("")
    formats = (export or {}).get("formats", profile["export"]["formats"])
    ext = next((f for f in ("pdf", "svg", "png") if f in formats), formats[0])
    graphic = f"{stem.name}.{ext}"
    number = caption.get("number", "X.X")
    lines = []
    if caption.get("zh"):
        lines.append(f"图{number} {caption['zh']}")
    if caption.get("en"):
        lines.append(f"Fig. {number} {caption['en']}")
    lines.append(f"[插入宽度 {width_mm:.1f} mm，100% 不缩放]")
    stem.with_suffix(".caption.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    label = caption.get("label", f"fig:{stem.name}")
    if profile.get("caption") == "bicaption":
        caption_line = f"\\bicaption{{{caption.get('zh', '')}}}{{{caption.get('en', '')}}}"
    else:
        caption_line = f"\\caption{{{caption.get('en', caption.get('zh', ''))}}}"
    text = (
        "\\begin{figure}[!ht]\n"
        "  \\centering\n"
        f"  \\includegraphics[width={width_mm:.1f}mm]{{{graphic}}}\n"
        f"  {caption_line}\n"
        f"  \\label{{{label}}}\n"
        "\\end{figure}\n"
    )
    path = stem.with_suffix(".tex")
    path.write_text(text, encoding="utf-8")
    return path


def figure_width_mm(fig: plt.Figure) -> float:
    return float(fig.get_figwidth() * MM_PER_INCH)
