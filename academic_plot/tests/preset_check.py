"""Regression check for locked map presets. Run after any change to plot_map.py, style.py or presets/.

1. Preset and land files must match the accepted bytes (hashes below).
2. Re-rendering the reference field must reproduce the accepted image (compared at 1/4 size).
Needs the real profile fonts (Windows: C:\\Windows\\Fonts). Exit 0 = consistent, 1 = drift.
A deliberate, user-approved preset change updates the hash and the reference image in the same commit.
"""
import hashlib
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plot_preset_map import PRESET_DIR, draw_preset  # noqa: E402

REF = Path(__file__).with_name("reference")
LOCKED = {  # accepted 2026-10-15 (south-china-sea return-level and climatology maps)
    "scs_field.json": "afb1dd2a14cae89c6ed6b091fde59e9f729808341a8778985e99e097c8291f6f",
    "land/scs_ne50m_land.geojson": "d1a7b04cf2a848b0cb834de96e796c864e3403e0d122d191195f3534b39dfc5d",
}
MAX_CHANGED_PCT = 0.1   # % of reduced-size pixels whose colour differs by more than 30/255


def quarter(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    return np.asarray(im.resize((im.width // 4, im.height // 4), Image.LANCZOS), int)


def main() -> None:
    ok = True
    for name, digest in LOCKED.items():
        actual = hashlib.sha256((PRESET_DIR / name).read_bytes()).hexdigest()
        if actual != digest:
            print(f"FAIL preset file changed: {name} sha256 {actual}")
            ok = False
    with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        draw_preset(REF / "scs_field_SE10.csv", tmp, preset="scs_field", scale="重现期波高", title="reference")
        new = quarter(Path(tmp) / "reference.png")
    old = np.asarray(Image.open(REF / "scs_field_SE10_quarter.png").convert("RGB"), int)
    if old.shape != new.shape:
        print(f"FAIL size changed: {old.shape} -> {new.shape}")
        ok = False
    else:
        changed = 100 * (np.abs(old - new).max(axis=2) > 30).mean()
        print(f"scs_field reference pixels changed: {changed:.3f}% (limit {MAX_CHANGED_PCT}%)")
        ok &= changed <= MAX_CHANGED_PCT
    print("PRESETS OK" if ok else "PRESET DRIFT: do not publish; ask the user")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
