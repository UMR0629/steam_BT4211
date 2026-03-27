import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from paths import FIGURES_DIR, PROCESSED_DATA_DIR


def load_data(coords_path: Path, clean_games_path: Path) -> pd.DataFrame:
    coords = pd.read_csv(coords_path, encoding="utf-8-sig")
    clean = pd.read_csv(clean_games_path, encoding="utf-8-sig")
    merged = coords.merge(
        clean[["appid", "name", "owners_low", "review_count", "owners_bucket"]],
        on=["appid", "name", "owners_bucket"],
        how="left",
    )
    merged["owners_low"] = pd.to_numeric(merged["owners_low"], errors="coerce").fillna(0)
    merged["review_count"] = pd.to_numeric(merged["review_count"], errors="coerce").fillna(0)
    return merged


def plot_with_labels(df: pd.DataFrame, top_n: int, out_path: Path) -> pd.DataFrame:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    label_df = (
        df.sort_values(["owners_low", "review_count"], ascending=[False, False])
        .drop_duplicates(subset=["appid"])
        .head(top_n)
        .copy()
    )

    bucket_order = sorted(df["owners_bucket"].dropna().unique().tolist())
    colors = plt.get_cmap("tab10")

    plt.figure(figsize=(13, 9))
    for idx, bucket in enumerate(bucket_order):
        subset = df[df["owners_bucket"] == bucket]
        plt.scatter(
            subset["umap1"],
            subset["umap2"],
            s=12,
            alpha=0.18,
            label=bucket,
            color=colors(idx % 10),
        )

    plt.scatter(
        label_df["umap1"],
        label_df["umap2"],
        s=42,
        color="#111111",
        alpha=0.9,
        marker="x",
    )

    for _, row in label_df.iterrows():
        plt.text(
            row["umap1"],
            row["umap2"],
            str(row["name"]),
            fontsize=8.5,
            ha="left",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.82, "edgecolor": "#666"},
        )

    plt.title("Steam Positioning Map (UMAP with Top-Sales Labels)")
    plt.xlabel("UMAP1")
    plt.ylabel("UMAP2")
    plt.legend(title="owners_bucket", fontsize=8, title_fontsize=9, loc="best")
    plt.grid(alpha=0.12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return label_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate UMAP with top-selling/famous games.")
    parser.add_argument(
        "--coords",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_umap_coords.csv"),
        help="Path to UMAP coordinates CSV.",
    )
    parser.add_argument(
        "--clean-games",
        type=str,
        default=str(PROCESSED_DATA_DIR / "clean_games.csv"),
        help="Path to clean_games.csv.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="How many top-selling games to label.",
    )
    parser.add_argument(
        "--plot-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_umap_top_games.png"),
        help="Output annotated plot path.",
    )
    parser.add_argument(
        "--labels-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "top_games_labels.csv"),
        help="Output CSV with labeled games.",
    )
    args = parser.parse_args()

    df = load_data(Path(args.coords), Path(args.clean_games))
    label_df = plot_with_labels(df, args.top_n, Path(args.plot_out))
    labels_out_path = Path(args.labels_out)
    labels_out_path.parent.mkdir(parents=True, exist_ok=True)
    label_df.to_csv(labels_out_path, index=False, encoding="utf-8-sig")

    print(f"Rows: {len(df)}")
    print(f"Labeled games: {len(label_df)}")
    print(f"Plot: {args.plot_out}")
    print(f"Labels: {args.labels_out}")


if __name__ == "__main__":
    main()
