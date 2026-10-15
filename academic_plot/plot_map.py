#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate fixed-geometry lon/lat field maps (Plate Carree) with a shared colorbar."""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

from plot_common import make_figure_axes
from style import (
    axes_box_mm,
    draw_label,
    export_figure,
    label_text,
    load_profile,
    panel_letter,
    setup_fonts,
    style_defaults,
    write_caption_snippet,
)

__version__ = "1.1.0"
MM = 1 / 25.4

# Extra space reserved outside the panel block for the colorbar (mm), per position.
COLORBAR_BLOCK_MM = {"bottom": 16.5, "right": 16.0}
PT = 25.4 / 72.0


# ---------------------------------------------------------------- data

def load_field(spec: dict[str, Any], base: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Return (lon, lat, values[lat, lon], missing) on the source grid, latitude ascending.

    missing marks CSV rows that exist but carry no value (e.g. an ocean cell with too few samples);
    cells absent from the CSV (land) are not missing. NetCDF cannot make the distinction: None.
    """
    path = (base / spec["input"]).resolve()
    if path.suffix.lower() == ".nc":
        import xarray as xr

        with xr.open_dataset(path) as ds:
            name = spec.get("var") or next(iter(ds.data_vars))
            array = ds[name].squeeze(drop=True).load()
        rename = {old: new for old, new in (("lat", "latitude"), ("lon", "longitude")) if old in array.dims}
        array = array.rename(rename).sortby("latitude").sortby("longitude")
        if array.dims != ("latitude", "longitude"):
            array = array.transpose("latitude", "longitude")
        return array.longitude.values, array.latitude.values, array.values.astype(float), None

    cols = spec.get("columns", {"lon": "lon", "lat": "lat", "value": "value"})
    frame = pd.read_csv(path)
    grid = frame.pivot(index=cols["lat"], columns=cols["lon"], values=cols["value"]).sort_index().sort_index(axis=1)
    present = frame.assign(_row=1).pivot(index=cols["lat"], columns=cols["lon"], values="_row").reindex_like(grid)
    missing = present.notna().to_numpy() & grid.isna().to_numpy()
    return grid.columns.to_numpy(float), grid.index.to_numpy(float), grid.to_numpy(float), missing


def display_smoothing(lon: np.ndarray, lat: np.ndarray, z: np.ndarray, cfg: dict[str, Any], missing: np.ndarray | None = None):
    """Display-only resampling + normalized Gaussian smoothing (never treats NaN as zero).

    Off by default. When used, state it in the figure caption. With `blank_missing`, display
    cells nearest to a missing source cell stay blank instead of being filled by neighbours.
    """
    from scipy.interpolate import RegularGridInterpolator
    from scipy.ndimage import gaussian_filter

    res = float(cfg.get("target_res_deg", 0.05))
    sigma = float(cfg.get("sigma", 2))
    # linspace keeps the last display point exactly on the source edge (arange can overshoot it).
    x = np.linspace(lon.min(), lon.max(), int(round((lon.max() - lon.min()) / res)) + 1)
    y = np.linspace(lat.min(), lat.max(), int(round((lat.max() - lat.min()) / res)) + 1)
    xx, yy = np.meshgrid(x, y)
    points = np.column_stack([yy.ravel(), xx.ravel()])
    valid = np.isfinite(z)
    value = RegularGridInterpolator((lat, lon), np.where(valid, z, 0.0))(points).reshape(xx.shape)
    support = RegularGridInterpolator((lat, lon), valid.astype(float))(points).reshape(xx.shape)
    num = gaussian_filter(value, sigma=sigma, mode="nearest")
    cov = gaussian_filter(support, sigma=sigma, mode="nearest")
    out = np.divide(num, cov, out=np.full_like(num, np.nan), where=cov > 1e-12)
    out[cov < float(cfg.get("min_support", 0.5))] = np.nan
    if cfg.get("blank_missing", False) and missing is not None and missing.any():
        near = RegularGridInterpolator((lat, lon), missing.astype(float), method="nearest")(points).reshape(xx.shape)
        out[near > 0.5] = np.nan
    return x, y, out


# ---------------------------------------------------------------- land

def _rings_to_path(polygons: list[list[list[list[float]]]]) -> MplPath:
    vertices, codes = [], []
    for polygon in polygons:
        for ring in polygon:
            ring = np.asarray(ring, float)[:, :2]
            vertices.extend(ring.tolist())
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 2) + [MplPath.CLOSEPOLY])
    return MplPath(vertices, codes)


def land_path(cfg: dict[str, Any], extent: list[float], base: Path, *, draft: bool) -> MplPath | None:
    source = cfg.get("source", "natural_earth")
    if source == "none":
        return None
    if source == "natural_earth":
        try:
            import cartopy.feature as cfeature
            from cartopy.mpl.patch import geos_to_path
            from shapely.geometry import box
        except ImportError as exc:
            if draft:
                warnings.warn(f"cartopy unavailable ({exc}); land omitted in draft.", RuntimeWarning, stacklevel=2)
                return None
            raise RuntimeError("land.source=natural_earth needs cartopy (and its cached Natural Earth data).") from exc
        clip = box(extent[0] - 1, extent[2] - 1, extent[1] + 1, extent[3] + 1)
        feature = cfeature.NaturalEarthFeature("physical", "land", cfg.get("scale", "10m"))
        paths = [p for geom in feature.geometries() if geom.intersects(clip) for p in geos_to_path(geom.intersection(clip))]
        return MplPath.make_compound_path(*paths) if paths else None

    data = json.loads((base / source).read_text(encoding="utf-8"))
    features = data["features"] if data.get("type") == "FeatureCollection" else [data]
    polygons = []
    for feature in features:
        geom = feature.get("geometry", feature)
        if geom["type"] == "Polygon":
            polygons.append(geom["coordinates"])
        elif geom["type"] == "MultiPolygon":
            polygons.extend(geom["coordinates"])
    return _rings_to_path(polygons)


# ---------------------------------------------------------------- axes helpers

def degree_label(value: float, axis: str) -> str:
    if abs(value) < 1e-9:
        return "0°"
    hemi = ("E" if value > 0 else "W") if axis == "x" else ("N" if value > 0 else "S")
    return f"{abs(value):g}°{hemi}"


def levels_from(cfg: dict[str, Any]) -> np.ndarray:
    levels = cfg["levels"]
    if isinstance(levels, dict):
        return np.arange(levels["start"], levels["stop"] + levels["step"] / 2, levels["step"])
    return np.asarray(levels, float)


def audit_field(z: np.ndarray, levels: np.ndarray, extend: str, name: str, mode: str) -> None:
    finite = z[np.isfinite(z)]
    if finite.size == 0:
        raise ValueError(f"{name}: no finite values.")
    low = finite.min() < levels[0] and extend not in {"min", "both"}
    high = finite.max() > levels[-1] and extend not in {"max", "both"}
    if not (low or high):
        return
    message = (
        f"{name}: data range [{finite.min():.4g}, {finite.max():.4g}] exceeds levels "
        f"[{levels[0]:.4g}, {levels[-1]:.4g}] with extend='{extend}'."
    )
    if mode == "error":
        raise ValueError(message)
    if mode == "warn":
        warnings.warn(message, RuntimeWarning, stacklevel=2)


def map_layout(config: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Derive the panel aspect from the lon/lat extent and reserve the colorbar block."""
    layout = json.loads(json.dumps(config["layout"]))
    geometry = layout.setdefault("geometry", {"profile": "academic_mm_v1"})
    west, east, south, north = config["map"]["extent"]
    geometry.setdefault("panel_aspect", (north - south) / (east - west))
    position = config.get("colorbar", {}).get("position", "bottom")
    # Maps carry no axis titles or legend: keep tick-label room only.
    base = profile["geometry_mm"]
    margin = {
        "left": base["ylabel_offset"] + 1.0,
        "right": base["margin"]["right"],
        "bottom": base["margin"]["bottom"] - base["bottom_band_y"] - 1.0,
        "top": 3.0,
    }
    margin.update(geometry.get("margin_mm", {}))
    if position in COLORBAR_BLOCK_MM:
        margin[position] += float(config.get("colorbar", {}).get("block_mm", COLORBAR_BLOCK_MM[position]))
    if config.get("panel_label_position", "top_left") == "below":
        geometry.setdefault("gap_mm", [profile["geometry_mm"]["gap"][0], profile["geometry_mm"]["gap"][1] + 5])
        margin["bottom"] += 5
    geometry["margin_mm"] = margin
    return layout


# ---------------------------------------------------------------- main

def draw_main(config: dict[str, Any], output: Path, base: Path, *, draft: bool = False, font_dir: Path | None = None) -> list[Path]:
    profile = load_profile(config.get("profile", "thesis_zh"))
    setup_fonts(profile, draft=draft, font_dir=font_dir)
    style = style_defaults(profile)
    style.update(config.get("style", {}))

    layout = map_layout(config, profile)
    rows, cols = int(layout["rows"]), int(layout["cols"])
    panels = config["panels"]
    if len(panels) > rows * cols:
        raise ValueError("Panel count exceeds rows × cols.")

    map_cfg = config["map"]
    west, east, south, north = map_cfg["extent"]
    field_cfg = config["field"]
    levels = levels_from(field_cfg)
    extend = field_cfg.get("extend", "neither")
    cmap = plt.get_cmap(field_cfg.get("cmap", "YlGnBu"))
    smoothing = config.get("display_smoothing", {})
    range_mode = str(config.get("range_guard", {}).get("mode", "error"))
    mode = field_cfg.get("render", "contourf")

    fig, axes, _, geometry = make_figure_axes(rows, cols, layout, profile)
    land = land_path(map_cfg.get("land", {}), map_cfg["extent"], base, draft=draft)
    land_cfg = map_cfg.get("land", {})
    mappable = None

    for index, panel in enumerate(panels):
        ax = axes.ravel()[index]
        row, col = divmod(index, cols)
        lon, lat, z, missing = load_field(panel, base)
        audit_field(z, levels, extend, panel["input"], range_mode)
        if smoothing.get("enabled", False):
            lon, lat, z = display_smoothing(lon, lat, z, smoothing, missing)
            warnings.warn(f"{panel['input']}: display smoothing applied; state it in the caption.", UserWarning, stacklevel=2)

        if mode == "pcolormesh":
            mappable = ax.pcolormesh(lon, lat, np.ma.masked_invalid(z), cmap=cmap, norm=BoundaryNorm(levels, cmap.N, extend=extend), shading="nearest")
        else:
            mappable = ax.contourf(lon, lat, np.ma.masked_invalid(z), levels=levels, cmap=cmap, extend=extend)
        mappable.set_rasterized(True)

        contours = field_cfg.get("contours")
        if contours:
            cs = ax.contour(lon, lat, np.ma.masked_invalid(z), levels=contours, colors=field_cfg.get("contour_color", "0.2"),
                            linewidths=style["contour_line_width"])
            if field_cfg.get("contour_labels", True):
                fmt = field_cfg.get("contour_label_format", "%g")
                ax.clabel(cs, fmt=fmt, fontsize=style["annotation_fontsize"], inline=True, inline_spacing=2)

        if land is not None:
            ax.add_patch(
                PathPatch(
                    land,
                    facecolor=land_cfg.get("facecolor", "#d9d9d9"),
                    edgecolor=land_cfg.get("edgecolor", "0.25"),
                    linewidth=style["coast_line_width"],
                    zorder=3,
                )
            )

        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_xticks(map_cfg["xticks"])
        ax.set_yticks(map_cfg["yticks"])
        ax.set_xticklabels([degree_label(v, "x") for v in map_cfg["xticks"]])
        ax.set_yticklabels([degree_label(v, "y") for v in map_cfg["yticks"]])
        ax.tick_params(
            labelsize=style["tick_fontsize"], width=style["tick_width"], length=style["tick_length"], pad=2,
            labelleft=col == 0, labelbottom=row == rows - 1 or config.get("x_ticklabels_all_rows", False),
        )
        if map_cfg.get("tick_direction") == "out":   # outward ticks on the labelled sides only
            ax.tick_params(direction="out", top=False, right=False)
        for spine in ax.spines.values():
            spine.set_linewidth(style["spine_width"])
            spine.set_zorder(5)

        text = panel_letter(index, profile) if config.get("panel_letters", len(panels) > 1) else ""
        if panel.get("label"):
            text = f"{text} {label_text(panel['label'], profile)}".strip()
        if text:
            if config.get("panel_label_position", "top_left") == "below":
                left, bottom, width, _ = axes_box_mm(fig, ax)
                draw_label(fig, text, left + width / 2, bottom - 7.5, fontsize=style["panel_label_fontsize"])
            else:
                ax.text(0.03, 0.97, text, transform=ax.transAxes, ha="left", va="top", zorder=6,
                        fontsize=style["panel_label_fontsize"],
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.0, "alpha": 0.85})

    for ax in axes.ravel()[len(panels):]:
        ax.set_visible(False)

    add_colorbar(fig, axes, geometry, mappable, levels, config, profile, style)

    width_mm = fig.get_figwidth() * 25.4
    written = export_figure(fig, output, profile=profile, fixed_geometry=True, draft=draft, qc=config.get("qc"), export=config.get("export"))
    snippet = write_caption_snippet(output, config.get("caption"), width_mm=width_mm, profile=profile, export=config.get("export"))
    return written + ([snippet] if snippet else [])


def add_colorbar(fig, axes, geometry, mappable, levels, config, profile, style) -> None:
    cfg = config.get("colorbar", {})
    position = cfg.get("position", "bottom")
    if position == "none" or mappable is None:
        return
    canvas_w, canvas_h = geometry["canvas_size_mm"]
    margin = geometry["margin_mm"]
    rows, cols = axes.shape
    panel_w, panel_h = geometry["panel_size_mm"]
    gap_x, gap_y = geometry["gap_mm"]
    block_w = cols * panel_w + (cols - 1) * gap_x
    block_h = rows * panel_h + (rows - 1) * gap_y
    thickness = float(cfg.get("thickness_mm", 2.5))
    ticks = config["field"].get("ticks")
    label = label_text(config["field"].get("label", ""), profile)
    below = 5.0 if config.get("panel_label_position", "top_left") == "below" else 0.0

    if position == "bottom":
        length = block_w * float(cfg.get("length_frac", 0.6 if cols > 1 else 0.85))
        x0 = margin["left"] + (block_w - length) / 2
        y0 = margin["bottom"] - below - float(cfg.get("pad_mm", 7.5)) - thickness
        cax = fig.add_axes([x0 / canvas_w, y0 / canvas_h, length / canvas_w, thickness / canvas_h])
        cb = fig.colorbar(mappable, cax=cax, orientation="horizontal", ticks=ticks)
        tick_pt, label_pt = style["tick_fontsize"], style["axis_label_fontsize"]
        offset = 0.7 + tick_pt * PT + 2.0 + 0.5 * label_pt * PT
        if label:
            draw_label(fig, label, x0 + length / 2, y0 - offset, fontsize=label_pt)
    else:
        length = block_h * float(cfg.get("length_frac", 0.85))
        x0 = margin["left"] + block_w + float(cfg.get("pad_mm", 3.0))
        y0 = margin["bottom"] + (block_h - length) / 2
        cax = fig.add_axes([x0 / canvas_w, y0 / canvas_h, thickness / canvas_w, length / canvas_h])
        cb = fig.colorbar(mappable, cax=cax, orientation="vertical", ticks=ticks)
        tick_pt, label_pt = style["tick_fontsize"], style["axis_label_fontsize"]
        offset = 0.7 + 2.0 * tick_pt * PT + 1.0 + 0.75 * label_pt * PT
        if label:
            draw_label(fig, label, x0 + thickness + offset, y0 + length / 2, fontsize=label_pt, rotation=90)
    cb.ax.tick_params(labelsize=style["tick_fontsize"], width=style["tick_width"], length=style["tick_length"],
                      direction=cfg.get("tick_direction", "in"))
    cb.minorticks_off()
    cb.outline.set_linewidth(style["spine_width"])
    if cb.solids is not None:
        cb.solids.set_rasterized(True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draft", action="store_true", help="Substitute fonts, stamp DRAFT, allow missing cartopy land.")
    parser.add_argument("--font-dir", type=Path, default=None)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for path in draw_main(config, args.output, args.config.parent, draft=args.draft, font_dir=args.font_dir):
        print(path)


if __name__ == "__main__":
    main()
