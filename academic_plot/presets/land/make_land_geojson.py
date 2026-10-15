"""Rebuild a preset land GeoJSON from a Natural Earth land shapefile (needs pyshp).

    python make_land_geojson.py <ne_50m_land.shp> --extent 105 121 8 25 --output scs_ne50m_land.geojson

Only polygons whose bounding box touches the extent (+1 deg) are kept; plot axes clip the rest.
scs_ne50m_land.geojson was made from Natural Earth 1:50m land v4.1.0 with the extent above.
"""
import argparse
import json
from pathlib import Path

import shapefile


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shapefile", type=Path)
    ap.add_argument("--extent", type=float, nargs=4, metavar=("W", "E", "S", "N"), required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    lon0, lon1, lat0, lat1 = args.extent
    polygons = []
    with shapefile.Reader(str(args.shapefile)) as reader:
        for shape in reader.iterShapes():
            x0, y0, x1, y1 = shape.bbox
            if x1 < lon0 - 1 or x0 > lon1 + 1 or y1 < lat0 - 1 or y0 > lat1 + 1:
                continue
            ends = list(shape.parts[1:]) + [len(shape.points)]
            rings = [[list(p) for p in shape.points[a:b]] for a, b in zip(shape.parts, ends)]
            polygons.append([ring + [ring[0]] if ring[0] != ring[-1] else ring for ring in rings])
    geometry = {"type": "MultiPolygon", "coordinates": polygons}
    args.output.write_text(json.dumps({"type": "Feature", "properties": {"source": "Natural Earth 1:50m land v4.1.0"},
                                       "geometry": geometry}), encoding="utf-8")
    print(args.output, len(polygons), "polygons")


if __name__ == "__main__":
    main()
