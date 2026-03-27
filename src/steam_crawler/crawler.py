import argparse
import csv
import html
import json
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from paths import RAW_DATA_DIR


STEAMSPY_BASE = "https://steamspy.com/api.php"
STEAM_STORE_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"


def build_session(timeout: int = 20) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
    )
    session.request_timeout = timeout
    return session


def get_json(session: requests.Session, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    resp = session.get(url, params=params, timeout=session.request_timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_steamspy_all(session: requests.Session) -> Dict[str, Dict[str, Any]]:
    return get_json(session, STEAMSPY_BASE, {"request": "all"})


def fetch_steamspy_all_page(session: requests.Session, page: int) -> Dict[str, Dict[str, Any]]:
    return get_json(session, STEAMSPY_BASE, {"request": "all", "page": page})


def fetch_steamspy_catalog(
    session: requests.Session,
    pages: int,
    page_delay: float,
) -> Dict[str, Dict[str, Any]]:
    if pages <= 1:
        return fetch_steamspy_all_page(session, 0)

    catalog: Dict[str, Dict[str, Any]] = {}
    for page in range(pages):
        page_data = fetch_steamspy_all_page(session, page)
        if not page_data:
            break
        catalog.update(page_data)

        # A short pause between pages helps reduce rate-limit errors.
        if page < pages - 1:
            time.sleep(page_delay)

    return catalog


def fetch_steamspy_appdetails(session: requests.Session, appid: int) -> Dict[str, Any]:
    return get_json(session, STEAMSPY_BASE, {"request": "appdetails", "appid": appid})


def fetch_store_api_details(session: requests.Session, appid: int) -> Dict[str, Any]:
    payload = get_json(
        session,
        STEAM_STORE_APPDETAILS_URL,
        {"appids": appid, "l": "english", "cc": "us"},
    )
    app_data = payload.get(str(appid), {})
    if not app_data.get("success"):
        return {}
    data = app_data.get("data")
    return data if isinstance(data, dict) else {}


def strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    unescaped = html.unescape(no_tags)
    compact = re.sub(r"\s+", " ", unescaped).strip()
    return compact


def parse_owners_lower_bound(owners: Any) -> int:
    if owners is None:
        return 0
    text = str(owners).replace(",", "").strip()
    m = re.match(r"(\d+)\s*\.\.\s*(\d+)", text)
    if m:
        return int(m.group(1))
    if text.isdigit():
        return int(text)
    return 0


def price_bucket(price_cents: Any) -> str:
    try:
        value = int(price_cents)
    except (TypeError, ValueError):
        value = 0

    if value <= 0:
        return "free_or_unknown"
    if value < 500:
        return "under_5"
    if value < 1500:
        return "5_to_15"
    if value < 3000:
        return "15_to_30"
    return "30_plus"


def owners_bucket(owners: Any) -> str:
    value = parse_owners_lower_bound(owners)
    if value < 1_000:
        return "lt_1k"
    if value < 10_000:
        return "1k_to_10k"
    if value < 100_000:
        return "10k_to_100k"
    if value < 1_000_000:
        return "100k_to_1m"
    return "1m_plus"


def stratified_sample_appids(
    all_data: Dict[str, Dict[str, Any]],
    sample_size: int,
    seed: int,
) -> List[int]:
    grouped: Dict[Tuple[str, str], List[int]] = {}
    for raw_appid, item in all_data.items():
        if not str(raw_appid).isdigit():
            continue
        appid = int(raw_appid)
        bucket = (
            owners_bucket(item.get("owners")),
            price_bucket(item.get("price")),
        )
        grouped.setdefault(bucket, []).append(appid)

    if not grouped:
        return []

    rng = random.Random(seed)
    for appids in grouped.values():
        rng.shuffle(appids)

    group_items = sorted(grouped.items(), key=lambda x: x[0])
    selected: List[int] = []
    seen = set()

    while len(selected) < sample_size:
        progressed = False
        for _, appids in group_items:
            if not appids:
                continue
            appid = appids.pop()
            if appid in seen:
                continue
            selected.append(appid)
            seen.add(appid)
            progressed = True
            if len(selected) >= sample_size:
                break
        if not progressed:
            break

    return selected


def parse_appids(raw: str) -> List[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    appids: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"Invalid appid: {part}")
        appids.append(int(part))
    return appids


def take_first_n_appids(all_data: Dict[str, Dict[str, Any]], n: int) -> List[int]:
    ids: List[int] = []
    for raw_appid in all_data.keys():
        if str(raw_appid).isdigit():
            ids.append(int(raw_appid))
        if len(ids) >= n:
            break
    return ids


def extract_price_fields(store_data: Dict[str, Any], steamspy_brief: Dict[str, Any]) -> Tuple[int, int]:
    price_overview = store_data.get("price_overview")
    if isinstance(price_overview, dict):
        final_price = price_overview.get("final")
        initial_price = price_overview.get("initial")
        if final_price is not None and initial_price is not None:
            return int(final_price), int(initial_price)

    def to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return to_int(steamspy_brief.get("price")), to_int(steamspy_brief.get("initialprice"))


def normalize_record(
    appid: int,
    steamspy_brief: Dict[str, Any],
    steamspy_detail: Dict[str, Any],
    store_data: Dict[str, Any],
) -> Dict[str, Any]:
    tags = steamspy_detail.get("tags")
    if not isinstance(tags, dict):
        tags = {}

    developers = store_data.get("developers")
    if not isinstance(developers, list):
        developers = []

    publishers = store_data.get("publishers")
    if not isinstance(publishers, list):
        publishers = []

    genres = store_data.get("genres")
    if isinstance(genres, list):
        genre_names = [item.get("description") for item in genres if isinstance(item, dict) and item.get("description")]
    else:
        genre_names = []

    categories = store_data.get("categories")
    if isinstance(categories, list):
        category_names = [item.get("description") for item in categories if isinstance(item, dict) and item.get("description")]
    else:
        category_names = []

    platforms = store_data.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}

    release_date = store_data.get("release_date")
    if not isinstance(release_date, dict):
        release_date = {}

    recommendations = store_data.get("recommendations")
    if not isinstance(recommendations, dict):
        recommendations = {}

    price_cents, initial_price_cents = extract_price_fields(store_data, steamspy_brief)

    return {
        "appid": appid,
        "name": steamspy_brief.get("name") or steamspy_detail.get("name") or store_data.get("name"),
        "type": store_data.get("type"),
        "is_free": bool(store_data.get("is_free", False)),
        "owners_range": steamspy_brief.get("owners") or steamspy_detail.get("owners"),
        "price_cents": price_cents,
        "initial_price_cents": initial_price_cents,
        "positive": steamspy_brief.get("positive") or steamspy_detail.get("positive"),
        "negative": steamspy_brief.get("negative") or steamspy_detail.get("negative"),
        "ccu": steamspy_brief.get("ccu") or steamspy_detail.get("ccu"),
        "average_forever": steamspy_detail.get("average_forever"),
        "median_forever": steamspy_detail.get("median_forever"),
        "average_2weeks": steamspy_detail.get("average_2weeks"),
        "median_2weeks": steamspy_detail.get("median_2weeks"),
        "languages": steamspy_detail.get("languages"),
        "tags": tags,
        "developers": developers,
        "publishers": publishers,
        "genres": genre_names,
        "categories": category_names,
        "short_description": store_data.get("short_description"),
        "about_the_game": strip_html(store_data.get("about_the_game", "")),
        "detailed_description": strip_html(store_data.get("detailed_description", "")),
        "release_date": release_date.get("date"),
        "coming_soon": bool(release_date.get("coming_soon", False)),
        "supported_languages": store_data.get("supported_languages"),
        "platforms": {
            "windows": bool(platforms.get("windows", False)),
            "mac": bool(platforms.get("mac", False)),
            "linux": bool(platforms.get("linux", False)),
        },
        "recommendations_total": recommendations.get("total"),
        "metacritic_score": (store_data.get("metacritic") or {}).get("score"),
        "website": store_data.get("website"),
        "header_image": store_data.get("header_image"),
    }


def write_json(path: str, rows: List[Dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(rows, file_obj, ensure_ascii=False, indent=2)


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "appid",
        "name",
        "type",
        "is_free",
        "owners_range",
        "price_cents",
        "initial_price_cents",
        "positive",
        "negative",
        "ccu",
        "average_forever",
        "median_forever",
        "average_2weeks",
        "median_2weeks",
        "languages",
        "release_date",
        "coming_soon",
        "supported_languages",
        "recommendations_total",
        "metacritic_score",
        "website",
        "developers_json",
        "publishers_json",
        "genres_json",
        "categories_json",
        "platforms_json",
        "tags_json",
        "short_description",
        "about_the_game",
        "detailed_description",
        "header_image",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "appid": row.get("appid"),
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "is_free": row.get("is_free"),
                    "owners_range": row.get("owners_range"),
                    "price_cents": row.get("price_cents"),
                    "initial_price_cents": row.get("initial_price_cents"),
                    "positive": row.get("positive"),
                    "negative": row.get("negative"),
                    "ccu": row.get("ccu"),
                    "average_forever": row.get("average_forever"),
                    "median_forever": row.get("median_forever"),
                    "average_2weeks": row.get("average_2weeks"),
                    "median_2weeks": row.get("median_2weeks"),
                    "languages": row.get("languages"),
                    "release_date": row.get("release_date"),
                    "coming_soon": row.get("coming_soon"),
                    "supported_languages": row.get("supported_languages"),
                    "recommendations_total": row.get("recommendations_total"),
                    "metacritic_score": row.get("metacritic_score"),
                    "website": row.get("website"),
                    "developers_json": json.dumps(row.get("developers", []), ensure_ascii=False),
                    "publishers_json": json.dumps(row.get("publishers", []), ensure_ascii=False),
                    "genres_json": json.dumps(row.get("genres", []), ensure_ascii=False),
                    "categories_json": json.dumps(row.get("categories", []), ensure_ascii=False),
                    "platforms_json": json.dumps(row.get("platforms", {}), ensure_ascii=False),
                    "tags_json": json.dumps(row.get("tags", {}), ensure_ascii=False),
                    "short_description": row.get("short_description"),
                    "about_the_game": row.get("about_the_game"),
                    "detailed_description": row.get("detailed_description"),
                    "header_image": row.get("header_image"),
                }
            )


def crawl(
    appids: Iterable[int],
    delay: float,
    timeout: int,
    progress_every: int,
    steamspy_catalog_pages: int,
    steamspy_page_delay: float,
) -> List[Dict[str, Any]]:
    session = build_session(timeout=timeout)
    all_data = fetch_steamspy_catalog(session, steamspy_catalog_pages, steamspy_page_delay)
    result: List[Dict[str, Any]] = []
    appid_list = list(appids)
    total = len(appid_list)

    for index, appid in enumerate(appid_list, start=1):
        brief = all_data.get(str(appid), {})
        try:
            steamspy_detail = fetch_steamspy_appdetails(session, appid)
            steamspy_status = "ok"
        except Exception as exc:
            steamspy_detail = {"_error": str(exc)}
            steamspy_status = "error"

        try:
            store_data = fetch_store_api_details(session, appid)
            store_status = "ok" if store_data else "empty"
        except Exception as exc:
            store_data = {}
            store_status = f"error:{exc}"

        row = normalize_record(appid, brief, steamspy_detail, store_data)
        result.append(row)

        if progress_every > 0 and (index % progress_every == 0 or index == total):
            percent = (index / total) * 100 if total else 100
            print(
                f"[{index}/{total}] {percent:6.2f}% "
                f"last_appid={appid} "
                f"name={row.get('name') or 'UNKNOWN'} "
                f"steamspy={steamspy_status} "
                f"store_api={store_status}"
            )

        if delay > 0:
            time.sleep(delay)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl Steam game data via SteamSpy + Steam Store API."
    )
    parser.add_argument(
        "--appids",
        type=str,
        default="",
        help="Comma-separated appids. Example: 730,570,1091500",
    )
    parser.add_argument(
        "--top-n-from-steamspy-all",
        type=int,
        default=0,
        help="If >0 and --appids is empty, crawl first N appids from SteamSpy 'all'.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="If >0 and --appids is empty, draw a stratified sample from SteamSpy 'all'.",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed for stratified sampling.",
    )
    parser.add_argument("--delay", type=float, default=0.8, help="Sleep seconds between apps.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument("--progress-every", type=int, default=50, help="Print progress every N games.")
    parser.add_argument(
        "--steamspy-catalog-pages",
        type=int,
        default=1,
        help="How many SteamSpy all-pages to load for the sampling/catalog pool. Each page is about 1000 apps.",
    )
    parser.add_argument(
        "--steamspy-page-delay",
        type=float,
        default=15.0,
        help="Sleep seconds between SteamSpy catalog pages.",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=str(RAW_DATA_DIR / "steam_games.json"),
        help="JSON output path.",
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default=str(RAW_DATA_DIR / "steam_games.csv"),
        help="CSV output path.",
    )
    args = parser.parse_args()

    if args.appids.strip():
        appids = parse_appids(args.appids)
    else:
        session = build_session(timeout=args.timeout)
        all_data = fetch_steamspy_catalog(
            session,
            args.steamspy_catalog_pages,
            args.steamspy_page_delay,
        )
        if args.sample_size > 0:
            appids = stratified_sample_appids(
                all_data=all_data,
                sample_size=args.sample_size,
                seed=args.sample_seed,
            )
        else:
            n = args.top_n_from_steamspy_all if args.top_n_from_steamspy_all > 0 else 20
            appids = take_first_n_appids(all_data, n)

    if not appids:
        raise RuntimeError("No appids to crawl. Please provide --appids or set a sampling option.")

    rows = crawl(
        appids=appids,
        delay=args.delay,
        timeout=args.timeout,
        progress_every=args.progress_every,
        steamspy_catalog_pages=args.steamspy_catalog_pages,
        steamspy_page_delay=args.steamspy_page_delay,
    )
    write_json(args.json_out, rows)
    write_csv(args.csv_out, rows)
    print(f"Done. Crawled {len(rows)} games.")
    print(f"JSON: {args.json_out}")
    print(f"CSV: {args.csv_out}")


if __name__ == "__main__":
    main()
