import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from paths import PROCESSED_DATA_DIR, RAW_DATA_DIR


DEFAULT_ALLOWED_TYPES = {"game"}
DEFAULT_GENERIC_TAGS = {
    "Action",
    "Adventure",
    "Indie",
    "Singleplayer",
    "Multiplayer",
    "RPG",
    "Simulation",
    "Strategy",
    "Casual",
}


def load_rows(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_owners_range(raw: Any) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    if not raw:
        return None, None, None
    text = str(raw).replace(",", "").strip()
    match = re.match(r"(\d+)\s*\.\.\s*(\d+)", text)
    if not match:
        return None, None, str(raw)
    low = int(match.group(1))
    high = int(match.group(2))
    return low, high, str(raw)


def owners_bucket(low: Optional[int]) -> str:
    if low is None:
        return "unknown"
    if low < 20_000:
        return "0_20k"
    if low < 50_000:
        return "20k_50k"
    if low < 100_000:
        return "50k_100k"
    if low < 200_000:
        return "100k_200k"
    if low < 500_000:
        return "200k_500k"
    if low < 1_000_000:
        return "500k_1m"
    if low < 2_000_000:
        return "1m_2m"
    if low < 5_000_000:
        return "2m_5m"
    return "5m_plus"


def parse_release_date(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    text = str(raw).strip()
    formats = [
        "%d %b, %Y",
        "%b %d, %Y",
        "%b %Y",
        "%Y",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_text_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def compute_tag_profile(tags: Dict[str, Any]) -> Tuple[Dict[str, float], float]:
    weighted: Dict[str, float] = {}
    total = 0.0
    for tag, raw_weight in (tags or {}).items():
        weight = math.log1p(max(safe_float(raw_weight), 0.0))
        if weight <= 0:
            continue
        weighted[str(tag)] = weight
        total += weight

    if total <= 0:
        return {}, 0.0

    normalized = {tag: weight / total for tag, weight in weighted.items()}
    return normalized, total


def clean_row(
    row: Dict[str, Any],
    allowed_types: Iterable[str],
    generic_tags: Iterable[str],
    as_of: datetime,
) -> Optional[Tuple[Dict[str, Any], Dict[str, float], Dict[str, float]]]:
    game_type = str(row.get("type") or "").strip().lower()
    if game_type not in set(allowed_types):
        return None

    owners_low, owners_high, owners_range = parse_owners_range(row.get("owners_range"))
    release_dt = parse_release_date(row.get("release_date"))
    release_age_days = (as_of - release_dt).days if release_dt else None

    positive = safe_int(row.get("positive"))
    negative = safe_int(row.get("negative"))
    review_count = positive + negative
    positive_ratio = (positive / review_count) if review_count > 0 else None

    price_cents = safe_int(row.get("price_cents"))
    is_free = bool(row.get("is_free")) or price_cents <= 0

    tags = row.get("tags")
    if not isinstance(tags, dict):
        tags = {}

    normalized_tags, tag_weight_sum = compute_tag_profile(tags)
    filtered_normalized_tags = {
        tag: value for tag, value in normalized_tags.items() if tag not in set(generic_tags)
    }

    cleaned = {
        "appid": row.get("appid"),
        "name": row.get("name"),
        "type": game_type,
        "owners_range": owners_range,
        "owners_low": owners_low,
        "owners_high": owners_high,
        "owners_bucket": owners_bucket(owners_low),
        "price_cents": price_cents,
        "price_usd": round(price_cents / 100.0, 2),
        "log_price": round(math.log1p(max(price_cents, 0)), 6),
        "is_free": int(is_free),
        "positive": positive,
        "negative": negative,
        "review_count": review_count,
        "positive_ratio": round(positive_ratio, 6) if positive_ratio is not None else None,
        "ccu": safe_int(row.get("ccu")),
        "log_ccu": round(math.log1p(max(safe_int(row.get("ccu")), 0)), 6),
        "average_forever": safe_int(row.get("average_forever")),
        "median_forever": safe_int(row.get("median_forever")),
        "average_2weeks": safe_int(row.get("average_2weeks")),
        "median_2weeks": safe_int(row.get("median_2weeks")),
        "log_average_forever": round(math.log1p(max(safe_int(row.get("average_forever")), 0)), 6),
        "release_date": row.get("release_date"),
        "release_age_days": release_age_days,
        "coming_soon": int(bool(row.get("coming_soon"))),
        "recommendations_total": safe_int(row.get("recommendations_total")),
        "log_recommendations_total": round(math.log1p(max(safe_int(row.get("recommendations_total")), 0)), 6),
        "metacritic_score": row.get("metacritic_score"),
        "windows": int(bool((row.get("platforms") or {}).get("windows"))),
        "mac": int(bool((row.get("platforms") or {}).get("mac"))),
        "linux": int(bool((row.get("platforms") or {}).get("linux"))),
        "genres_json": json.dumps(normalize_text_list(row.get("genres")), ensure_ascii=False),
        "categories_json": json.dumps(normalize_text_list(row.get("categories")), ensure_ascii=False),
        "developers_json": json.dumps(normalize_text_list(row.get("developers")), ensure_ascii=False),
        "publishers_json": json.dumps(normalize_text_list(row.get("publishers")), ensure_ascii=False),
        "tag_count_raw": len(tags),
        "tag_weight_sum_log": round(tag_weight_sum, 6),
        "tag_count_filtered": len(filtered_normalized_tags),
        "short_description": row.get("short_description"),
    }

    return cleaned, normalized_tags, filtered_normalized_tags


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_tag_stats(
    profiles: List[Dict[str, float]],
    filtered_profiles: List[Dict[str, float]],
    min_games: int,
    max_share: float,
) -> List[Dict[str, Any]]:
    game_count = len(profiles)
    raw_doc_freq = Counter()
    filtered_doc_freq = Counter()
    raw_total_weight = Counter()
    filtered_total_weight = Counter()

    for profile in profiles:
        for tag, value in profile.items():
            raw_doc_freq[tag] += 1
            raw_total_weight[tag] += value

    for profile in filtered_profiles:
        for tag, value in profile.items():
            filtered_doc_freq[tag] += 1
            filtered_total_weight[tag] += value

    tags = sorted(raw_doc_freq.keys())
    rows: List[Dict[str, Any]] = []
    for tag in tags:
        doc_freq = raw_doc_freq[tag]
        share = (doc_freq / game_count) if game_count else 0.0
        keep = doc_freq >= min_games and share <= max_share
        rows.append(
            {
                "tag": tag,
                "doc_freq_games": doc_freq,
                "doc_share": round(share, 6),
                "total_weight_normalized": round(raw_total_weight[tag], 6),
                "filtered_doc_freq_games": filtered_doc_freq.get(tag, 0),
                "filtered_total_weight_normalized": round(filtered_total_weight.get(tag, 0.0), 6),
                "suggest_keep": int(keep),
                "drop_reason": (
                    "too_rare" if doc_freq < min_games else
                    "too_common" if share > max_share else
                    ""
                ),
            }
        )
    rows.sort(key=lambda item: (-item["doc_freq_games"], item["tag"]))
    return rows


def build_tag_matrix_rows(
    cleaned_rows: List[Dict[str, Any]],
    profiles: List[Dict[str, float]],
    kept_tags: List[str],
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for cleaned, profile in zip(cleaned_rows, profiles):
        row = {
            "appid": cleaned["appid"],
            "name": cleaned["name"],
            "owners_bucket": cleaned["owners_bucket"],
            "price_usd": cleaned["price_usd"],
            "is_free": cleaned["is_free"],
        }
        for tag in kept_tags:
            row[f"tag::{tag}"] = round(profile.get(tag, 0.0), 6)
        output.append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and featurize Steam game data for positioning.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(RAW_DATA_DIR / "sample_5000.json"),
        help="Input JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(PROCESSED_DATA_DIR),
        help="Output directory.",
    )
    parser.add_argument("--min-tag-games", type=int, default=10, help="Minimum number of games a tag must appear in.")
    parser.add_argument("--max-tag-share", type=float, default=0.7, help="Maximum share of games a tag can appear in.")
    parser.add_argument(
        "--drop-generic-tags",
        type=str,
        default=",".join(sorted(DEFAULT_GENERIC_TAGS)),
        help="Comma-separated generic tags to drop from filtered tag profiles.",
    )
    parser.add_argument(
        "--allowed-types",
        type=str,
        default=",".join(sorted(DEFAULT_ALLOWED_TYPES)),
        help="Comma-separated Steam app types to keep.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    allowed_types = {item.strip().lower() for item in args.allowed_types.split(",") if item.strip()}
    generic_tags = {item.strip() for item in args.drop_generic_tags.split(",") if item.strip()}

    rows = load_rows(input_path)
    as_of = datetime.now(timezone.utc)

    cleaned_rows: List[Dict[str, Any]] = []
    raw_profiles: List[Dict[str, float]] = []
    filtered_profiles: List[Dict[str, float]] = []

    for row in rows:
        result = clean_row(row, allowed_types=allowed_types, generic_tags=generic_tags, as_of=as_of)
        if result is None:
            continue
        cleaned, raw_profile, filtered_profile = result
        cleaned_rows.append(cleaned)
        raw_profiles.append(raw_profile)
        filtered_profiles.append(filtered_profile)

    tag_stats = build_tag_stats(
        profiles=raw_profiles,
        filtered_profiles=filtered_profiles,
        min_games=args.min_tag_games,
        max_share=args.max_tag_share,
    )
    kept_tags = [row["tag"] for row in tag_stats if row["suggest_keep"] == 1 and row["filtered_doc_freq_games"] > 0]

    tag_matrix_rows = build_tag_matrix_rows(cleaned_rows, filtered_profiles, kept_tags)

    write_csv(out_dir / "clean_games.csv", cleaned_rows)
    write_csv(out_dir / "tag_stats.csv", tag_stats)
    write_csv(out_dir / "tag_matrix.csv", tag_matrix_rows)

    metadata = {
        "input": str(input_path),
        "output_dir": str(out_dir),
        "input_rows": len(rows),
        "kept_rows": len(cleaned_rows),
        "allowed_types": sorted(allowed_types),
        "generic_tags_dropped": sorted(generic_tags),
        "min_tag_games": args.min_tag_games,
        "max_tag_share": args.max_tag_share,
        "kept_tag_count": len(kept_tags),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input rows: {len(rows)}")
    print(f"Kept rows: {len(cleaned_rows)}")
    print(f"Kept tags: {len(kept_tags)}")
    print(f"Output dir: {out_dir}")


if __name__ == "__main__":
    main()
