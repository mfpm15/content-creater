"""Measure burned-in caption pixels and build reproducible visual contact sheets."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

PROJECT = Path(os.environ.get(
    "CLIPPER_VALIDATION_PROJECT",
    Path.home() / "ClipperCuan" / "projects" / "20261027-073927-9a67",
))
AUDIT = Path(os.environ.get(
    "CLIPPER_VALIDATION_AUDIT",
    PROJECT / "caption_clean_validation_20261027_095710",
))
VARIANTS = ("viral_pop", "box_punch", "neon_karaoke")


def read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def caption_bbox(raw: np.ndarray, styled: np.ndarray) -> dict:
    delta = cv2.absdiff(raw, styled)
    gray = cv2.cvtColor(delta, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(gray)
    mask[int(gray.shape[0] * .48):int(gray.shape[0] * .90), :] = 255
    changed = cv2.inRange(gray, 18, 255)
    changed = cv2.bitwise_and(changed, mask)
    changed = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(changed, 8)
    keep = np.zeros_like(changed)
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if area >= 12 and h >= 3:
            keep[labels == index] = 255
    points = cv2.findNonZero(keep)
    if points is None:
        return {"visible": False, "changed_pixels": 0}
    x, y, w, h = cv2.boundingRect(points)
    return {
        "visible": True,
        "x": int(x), "y": int(y), "width": int(w), "height": int(h),
        "width_pct": round(w / styled.shape[1] * 100, 2),
        "height_pct": round(h / styled.shape[0] * 100, 2),
        "center_y_pct": round((y + h / 2) / styled.shape[0] * 100, 2),
        "bottom_clearance_pct": round((styled.shape[0] - y - h) / styled.shape[0] * 100, 2),
        "changed_pixels": int(np.count_nonzero(keep)),
    }


def labeled_tile(image: np.ndarray, label: str, width: int = 270) -> np.ndarray:
    height = round(image.shape[0] * width / image.shape[1])
    tile = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    cv2.rectangle(tile, (0, 0), (width, 34), (5, 7, 10), -1)
    cv2.putText(tile, label, (9, 23), cv2.FONT_HERSHEY_SIMPLEX, .46, (255, 255, 255), 1, cv2.LINE_AA)
    return tile


def contact_sheet(tiles: list[np.ndarray], columns: int = 4, gap: int = 8) -> np.ndarray:
    rows = (len(tiles) + columns - 1) // columns
    cell_h = max(tile.shape[0] for tile in tiles)
    cell_w = max(tile.shape[1] for tile in tiles)
    sheet = np.full((rows * cell_h + (rows + 1) * gap, columns * cell_w + (columns + 1) * gap, 3), 18, np.uint8)
    for index, tile in enumerate(tiles):
        row, column = divmod(index, columns)
        y = gap + row * (cell_h + gap)
        x = gap + column * (cell_w + gap)
        sheet[y:y + tile.shape[0], x:x + tile.shape[1]] = tile
    return sheet


def main() -> int:
    report_path = AUDIT / "validation-report.json"
    report = json.loads(report_path.read_text("utf-8"))
    raw_frames = AUDIT / "raw_measurement_reference" / "frames"
    measurements: dict[str, dict] = {}
    comparison_tiles: list[np.ndarray] = []

    for variant in VARIANTS:
        result = report["results"][variant]
        frame_dir = AUDIT / variant / "frames"
        rows = []
        variant_tiles = []
        for record in result["frames"]:
            full_name = record["full"]
            raw = read_image(raw_frames / full_name)
            styled = read_image(frame_dir / full_name)
            metric = caption_bbox(raw, styled)
            rows.append({"index": record["index"], "timestamp": record["timestamp"], **metric})
            label = f"{variant}  {record['timestamp']:.2f}s"
            variant_tiles.append(labeled_tile(styled, label))
        visible = [row for row in rows if row.get("visible")]
        summary = {
            "template_id": result.get("template_id"),
            "template_name": result.get("template_name"),
            "nominal_ass_size": (result.get("caption_render") or {}).get("ass_size"),
            "estimated_height_pct": result.get("effective_caption_height_pct"),
            "sample_count": len(rows),
            "visible_sample_count": len(visible),
            "measured_height_px_min": min((row["height"] for row in visible), default=0),
            "measured_height_px_max": max((row["height"] for row in visible), default=0),
            "measured_height_px_median": round(float(np.median([row["height"] for row in visible])), 1) if visible else 0,
            "measured_height_pct_median": round(float(np.median([row["height_pct"] for row in visible])), 2) if visible else 0,
            "measured_bottom_clearance_pct_min": min((row["bottom_clearance_pct"] for row in visible), default=0),
            "frames": rows,
        }
        measurements[variant] = summary
        variant_sheet = contact_sheet(variant_tiles, 4)
        cv2.imwrite(str(AUDIT / f"contact_sheet_{variant}.jpg"), variant_sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])

    for index, record in enumerate(report["results"]["viral_pop"]["frames"]):
        for variant in VARIANTS:
            frame = read_image(AUDIT / variant / "frames" / record["full"])
            comparison_tiles.append(labeled_tile(frame, f"{variant}  {record['timestamp']:.2f}s", 240))
    cv2.imwrite(str(AUDIT / "contact_sheet_ab_comparison.jpg"), contact_sheet(comparison_tiles, 6), [cv2.IMWRITE_JPEG_QUALITY, 92])

    report["pixel_measurement_method"] = {
        "reference": "raw_measurement_reference",
        "threshold": "absolute luma difference >= 18",
        "region": "48%-90% of frame height",
        "component_filter": "area >= 12 px and height >= 3 px",
        "note": "Frame-difference metric measures pixels introduced by caption render on otherwise identical frames.",
    }
    report["caption_pixel_measurements"] = measurements
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    (AUDIT / "caption-pixel-measurements.json").write_text(json.dumps(measurements, ensure_ascii=False, indent=2), "utf-8")
    print(f"AUDIT_DIR={AUDIT}")
    for variant, summary in measurements.items():
        print(f"{variant}: template={summary['template_name']} size={summary['nominal_ass_size']} median={summary['measured_height_px_median']}px ({summary['measured_height_pct_median']}%) bottom_min={summary['measured_bottom_clearance_pct_min']}%")
    print(f"COMPARISON={AUDIT / 'contact_sheet_ab_comparison.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
