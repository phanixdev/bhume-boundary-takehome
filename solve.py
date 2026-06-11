#!/usr/bin/env python3
"""Conservative Malatavadi solver.

The method is intentionally simple and reproducible:

1. Keep each official plot shape unchanged.
2. Try small translations around the official position.
3. Score each translated outline against the rough boundary raster and the
   satellite image gradient.
4. Correct only when the best translation clearly beats the original; otherwise
   flag the plot and keep the official geometry.

This is a Silver/Gold style attempt: restrained corrections with confidence
based on signal strength, margin, area sanity, and shift size.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from scipy import ndimage
from shapely.affinity import translate
from shapely.geometry import MultiLineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform

from bhume import load, score, write_predictions
from bhume.geo import geom_to_imagery_crs


DEFAULT_VILLAGE = 'data/12429_malatavadi_chandgad_kolhapur'


@dataclass(frozen=True)
class RasterSignal:
    values: np.ndarray
    transform: object


@dataclass(frozen=True)
class Decision:
    status: str
    dx: float
    dy: float
    confidence: float | None
    best_signal: float
    original_signal: float
    margin: float
    area_ratio: float | None
    method_note: str


def robust_unit(arr: np.ndarray) -> np.ndarray:
    """Scale a raster to roughly [0, 1] while ignoring extreme bright pixels."""
    arr = arr.astype('float32')
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return np.zeros_like(arr, dtype='float32')
    lo = float(np.percentile(finite, 1))
    hi = float(np.percentile(finite, 99))
    if hi <= lo:
        hi = float(finite.max()) if finite.max() > lo else lo + 1.0
    return np.clip((arr - lo) / (hi - lo), 0, 1).astype('float32')


def load_boundary_signal(path: Path) -> RasterSignal:
    with rasterio.open(path) as src:
        band = src.read(1)
        return RasterSignal(robust_unit(band), src.transform)


def load_image_edge_signal(path: Path) -> RasterSignal:
    with rasterio.open(path) as src:
        rgb = src.read([1, 2, 3]).astype('float32')
        gray = rgb.mean(axis=0)
        sx = ndimage.sobel(gray, axis=1, mode='nearest')
        sy = ndimage.sobel(gray, axis=0, mode='nearest')
        grad = np.hypot(sx, sy)
        return RasterSignal(robust_unit(grad), src.transform)


def iter_lines(geom: BaseGeometry):
    boundary = geom.boundary
    if boundary.is_empty:
        return
    if isinstance(boundary, MultiLineString):
        yield from boundary.geoms
    elif hasattr(boundary, 'geoms'):
        for part in boundary.geoms:
            if part.geom_type in ('LineString', 'LinearRing'):
                yield part
    else:
        yield boundary


def sample_boundary_points(geom: BaseGeometry, spacing_m: float = 3.0, max_points: int = 180) -> np.ndarray:
    """Return representative (x, y) points along a polygon boundary in imagery CRS."""
    chunks = []
    for line in iter_lines(geom):
        length = float(line.length)
        if length <= 0:
            continue
        n = max(6, min(max_points, int(math.ceil(length / spacing_m))))
        distances = np.linspace(0, length, n, endpoint=False)
        chunks.extend(line.interpolate(float(d)) for d in distances)
    if not chunks:
        return np.empty((0, 2), dtype='float32')
    if len(chunks) > max_points:
        idx = np.linspace(0, len(chunks) - 1, max_points).astype(int)
        chunks = [chunks[i] for i in idx]
    return np.array([(p.x, p.y) for p in chunks], dtype='float32')


def bilinear_sample(signal: RasterSignal, xs: np.ndarray, ys: np.ndarray) -> float:
    """Sample a normalized raster at map coordinates and return mean intensity."""
    cols, rows = (~signal.transform) * (xs, ys)
    rows = np.asarray(rows, dtype='float32')
    cols = np.asarray(cols, dtype='float32')

    r0 = np.floor(rows).astype(int)
    c0 = np.floor(cols).astype(int)
    r1 = r0 + 1
    c1 = c0 + 1
    valid = (r0 >= 0) & (c0 >= 0) & (r1 < signal.values.shape[0]) & (c1 < signal.values.shape[1])
    if not np.any(valid):
        return 0.0

    rv = rows[valid]
    cv = cols[valid]
    r0v = r0[valid]
    c0v = c0[valid]
    r1v = r1[valid]
    c1v = c1[valid]
    wr = rv - r0v
    wc = cv - c0v

    a = signal.values[r0v, c0v]
    b = signal.values[r0v, c1v]
    c = signal.values[r1v, c0v]
    d = signal.values[r1v, c1v]
    vals = (a * (1 - wc) * (1 - wr)) + (b * wc * (1 - wr)) + (c * (1 - wc) * wr) + (d * wc * wr)
    return float(np.mean(vals))


def combined_signal(boundary: RasterSignal, image_edges: RasterSignal, xs: np.ndarray, ys: np.ndarray) -> float:
    b = bilinear_sample(boundary, xs, ys)
    e = bilinear_sample(image_edges, xs, ys)
    return (0.72 * b) + (0.28 * e)


def candidate_shifts(max_shift_m: float, step_m: float) -> list[tuple[float, float, float]]:
    vals = np.arange(-max_shift_m, max_shift_m + 0.001, step_m)
    shifts = []
    for dx in vals:
        for dy in vals:
            dist = float(math.hypot(dx, dy))
            if dist <= max_shift_m + 0.001:
                shifts.append((float(dx), float(dy), dist))
    shifts.sort(key=lambda x: x[2])
    return shifts


def area_ratio_for(row) -> float | None:
    total = row.get('recorded_area_sqm')
    kharaba = row.get('pot_kharaba_ha')
    if total is None or not np.isfinite(total) or total <= 0:
        return None
    if kharaba is not None and np.isfinite(kharaba):
        total += float(kharaba) * 10000.0
    if total <= 0:
        return None
    return float(row.get('map_area_sqm', 0.0)) / float(total)


def area_factor(ratio: float | None) -> float:
    if ratio is None:
        return 0.70
    # Close to one is best; extreme shape/record disagreement is risky.
    return float(np.clip(1.0 - abs(math.log(max(ratio, 0.05))) / math.log(1.8), 0.20, 1.0))


def confidence_from(best: float, margin: float, shift_dist: float, ratio: float | None, max_shift_m: float) -> float:
    signal_term = np.clip((best - 0.14) / 0.36, 0, 1)
    margin_term = np.clip((margin - 0.020) / 0.115, 0, 1)
    shift_term = np.clip(1.0 - (shift_dist / (max_shift_m * 1.15)), 0, 1)
    conf = (0.30 * signal_term) + (0.42 * margin_term) + (0.18 * shift_term) + (0.10 * area_factor(ratio))
    return float(np.clip(0.35 + 0.60 * conf, 0.35, 0.95))


def decide_plot(
    points_xy: np.ndarray,
    row,
    shifts: list[tuple[float, float, float]],
    boundary: RasterSignal,
    image_edges: RasterSignal,
    max_shift_m: float,
) -> Decision:
    ratio = area_ratio_for(row)
    if points_xy.size == 0:
        return Decision('flagged', 0, 0, None, 0, 0, 0, ratio, 'flagged: empty geometry boundary')

    xs0 = points_xy[:, 0]
    ys0 = points_xy[:, 1]
    original = combined_signal(boundary, image_edges, xs0, ys0)

    best_score = -1.0
    best_signal = 0.0
    best_dx = 0.0
    best_dy = 0.0
    best_dist = 0.0
    for dx, dy, dist in shifts:
        signal = combined_signal(boundary, image_edges, xs0 + dx, ys0 + dy)
        shift_penalty = 0.055 * (dist / max_shift_m)
        # A tiny preference for the official position avoids pointless sub-metre moves.
        score_value = signal - shift_penalty
        if score_value > best_score:
            best_score = score_value
            best_signal = signal
            best_dx = dx
            best_dy = dy
            best_dist = dist

    margin = best_signal - original
    af = area_factor(ratio)
    area_risky = ratio is None or ratio < 0.70 or ratio > 1.35
    min_margin = 0.045 if not area_risky else 0.080
    min_signal = 0.20 if not area_risky else 0.28

    large_shift_risky = best_dist > 14.0 and not (best_signal >= 0.34 and margin >= 0.18)

    if best_dist < 1.0:
        note = f'flagged: original already strongest; edge_signal={original:.3f}; area_ratio={fmt_ratio(ratio)}'
        return Decision('flagged', 0, 0, None, best_signal, original, margin, ratio, note)
    if margin < min_margin or best_signal < min_signal or af < 0.22 or large_shift_risky:
        reason = 'large shift without exceptional evidence' if large_shift_risky else 'weak/ambiguous alignment'
        note = (
            f'flagged: {reason}; best_shift=({best_dx:.1f},{best_dy:.1f})m; '
            f'margin={margin:.3f}; signal={best_signal:.3f}; area_ratio={fmt_ratio(ratio)}'
        )
        return Decision('flagged', 0, 0, None, best_signal, original, margin, ratio, note)

    conf = confidence_from(best_signal, margin, best_dist, ratio, max_shift_m)
    note = (
        f'translation-only edge alignment; shift=({best_dx:.1f},{best_dy:.1f})m; '
        f'margin={margin:.3f}; signal={best_signal:.3f}; area_ratio={fmt_ratio(ratio)}'
    )
    return Decision('corrected', best_dx, best_dy, conf, best_signal, original, margin, ratio, note)


def fmt_ratio(ratio: float | None) -> str:
    return 'unknown' if ratio is None else f'{ratio:.2f}'


def solve(village_dir: Path, max_shift_m: float, step_m: float, limit: int | None = None) -> gpd.GeoDataFrame:
    village = load(village_dir)
    if village.boundaries_path is None:
        raise FileNotFoundError('boundaries.tif is required for this solver')

    boundary = load_boundary_signal(village.boundaries_path)
    image_edges = load_image_edge_signal(village.imagery_path)
    shifts = candidate_shifts(max_shift_m=max_shift_m, step_m=step_m)

    rows = []
    with rasterio.open(village.imagery_path) as imagery_src:
        to_lonlat = Transformer.from_crs(imagery_src.crs, 'EPSG:4326', always_xy=True)
        for i, (plot_number, row) in enumerate(village.plots.iterrows(), start=1):
            if limit is not None and i > limit:
                break
            geom_img = geom_to_imagery_crs(imagery_src, row.geometry)
            points = sample_boundary_points(geom_img)
            decision = decide_plot(points, row, shifts, boundary, image_edges, max_shift_m)

            if decision.status == 'corrected':
                corrected_img = translate(geom_img, xoff=decision.dx, yoff=decision.dy)
                geom_out = shp_transform(lambda xs, ys, z=None: to_lonlat.transform(xs, ys), corrected_img)
            else:
                geom_out = row.geometry

            rows.append({
                'plot_number': str(plot_number),
                'status': decision.status,
                'confidence': decision.confidence,
                'method_note': decision.method_note,
                'geometry': geom_out,
            })

            if i % 250 == 0:
                corrected = sum(r['status'] == 'corrected' for r in rows)
                print(f'processed {i:4d}/{len(village.plots)} plots; corrected={corrected}')

    preds = gpd.GeoDataFrame(rows, geometry='geometry', crs='EPSG:4326')
    return preds


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Malatavadi predictions.geojson')
    parser.add_argument('village_dir', nargs='?', default=DEFAULT_VILLAGE)
    parser.add_argument('--max-shift-m', type=float, default=20.0)
    parser.add_argument('--step-m', type=float, default=2.0)
    parser.add_argument('--limit', type=int, default=None, help='debug: only process first N plots')
    args = parser.parse_args()

    village_dir = Path(args.village_dir)
    preds = solve(village_dir, max_shift_m=args.max_shift_m, step_m=args.step_m, limit=args.limit)
    out = write_predictions(village_dir / 'predictions.geojson', preds)

    n_corrected = int((preds['status'] == 'corrected').sum())
    n_flagged = int((preds['status'] == 'flagged').sum())
    print(f'wrote {out}')
    print(f'coverage: {n_corrected} corrected, {n_flagged} flagged')

    village = load(village_dir)
    if village.example_truths is not None:
        print()
        print(score(preds, village))
    else:
        print('no example_truths.geojson found; upload predictions.geojson on the Bhume Test page for scoring')


if __name__ == '__main__':
    main()
