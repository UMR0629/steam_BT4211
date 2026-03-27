import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from paths import PROCESSED_DATA_DIR


BASE_COLUMNS = ["appid", "name", "owners_bucket", "price_usd", "is_free"]
TAG_PREFIX = "tag::"


def load_mapping(path: Path) -> Dict[str, Tuple[str, str, int]]:
    mapping: Dict[str, Tuple[str, str, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            tag = (row.get("tag") or "").strip()
            merge_target = (row.get("merge_target") or "").strip()
            dimension = (row.get("dimension") or "").strip()
            keep_distinct = int(row.get("keep_distinct") or 0)
            if not tag or not merge_target:
                continue
            mapping[tag] = (merge_target, dimension, keep_distinct)
    return mapping


def load_tag_matrix(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def aggregate_rows(
    rows: List[Dict[str, str]],
    mapping: Dict[str, Tuple[str, str, int]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    taxonomy_features = set()
    dimension_counts = defaultdict(int)
    aggregated_rows: List[Dict[str, object]] = []

    for row in rows:
        out: Dict[str, object] = {col: row.get(col) for col in BASE_COLUMNS}
        aggregated = defaultdict(float)

        for key, raw_value in row.items():
            if not key.startswith(TAG_PREFIX):
                continue
            tag = key[len(TAG_PREFIX):]
            if tag not in mapping:
                continue
            merge_target, dimension, keep_distinct = mapping[tag]
            feature_name = f"tax::{dimension}::{merge_target}"
            try:
                value = float(raw_value or 0.0)
            except ValueError:
                value = 0.0
            if value <= 0:
                continue
            aggregated[feature_name] += value
            taxonomy_features.add(feature_name)
            dimension_counts[dimension] += 1

        for feature_name, value in aggregated.items():
            out[feature_name] = round(value, 6)

        aggregated_rows.append(out)

    ordered_features = sorted(taxonomy_features)
    dense_rows: List[Dict[str, object]] = []
    for row in aggregated_rows:
        dense = {col: row.get(col) for col in BASE_COLUMNS}
        for feature in ordered_features:
            dense[feature] = row.get(feature, 0.0)
        dense_rows.append(dense)

    feature_stats = []
    for feature in ordered_features:
        _, dimension, bucket = feature.split("::", 2)
        feature_stats.append(
            {
                "feature": feature,
                "dimension": dimension,
                "bucket": bucket,
            }
        )

    return dense_rows, feature_stats


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate tag_matrix.csv into taxonomy-level features.")
    parser.add_argument(
        "--tag-matrix",
        type=str,
        default=str(PROCESSED_DATA_DIR / "tag_matrix.csv"),
        help="Path to tag_matrix.csv",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_mapping.csv"),
        help="Path to taxonomy_mapping.csv",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--feature-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_features.csv"),
        help="Output feature dictionary CSV path",
    )
    args = parser.parse_args()

    mapping = load_mapping(Path(args.mapping))
    tag_rows = load_tag_matrix(Path(args.tag_matrix))
    taxonomy_rows, feature_rows = aggregate_rows(tag_rows, mapping)
    write_csv(Path(args.out), taxonomy_rows)
    write_csv(Path(args.feature_out), feature_rows)

    print(f"Input rows: {len(tag_rows)}")
    print(f"Mapping tags: {len(mapping)}")
    print(f"Output rows: {len(taxonomy_rows)}")
    print(f"Taxonomy features: {len(feature_rows)}")
    print(f"Output file: {args.out}")


if __name__ == "__main__":
    main()
