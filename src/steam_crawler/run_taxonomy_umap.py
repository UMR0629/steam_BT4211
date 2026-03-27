import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from paths import FIGURES_DIR, PROCESSED_DATA_DIR

try:
    import umap
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: umap-learn. Install it with `pip install umap-learn` in your venv."
    ) from exc


META_COLUMNS = ["appid", "name", "owners_bucket", "price_usd", "is_free"]
FEATURE_PREFIX = "tax::"


def load_matrix(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def run_umap(
    df: pd.DataFrame,
    n_neighbors: int,
    min_dist: float,
    random_state: int,
) -> pd.DataFrame:
    feature_cols = [col for col in df.columns if col.startswith(FEATURE_PREFIX)]
    features = df[feature_cols].copy()

    imputer = SimpleImputer(strategy="constant", fill_value=0.0)
    X = imputer.fit_transform(features)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric="euclidean",
        random_state=random_state,
    )
    coords = reducer.fit_transform(X_scaled)

    out = df[META_COLUMNS].copy()
    out["umap1"] = coords[:, 0]
    out["umap2"] = coords[:, 1]
    return out


def plot_scatter(path: Path, coords_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bucket_order = sorted(coords_df["owners_bucket"].dropna().unique().tolist())
    colors = plt.get_cmap("tab10")

    plt.figure(figsize=(12, 8))
    for idx, bucket in enumerate(bucket_order):
        subset = coords_df[coords_df["owners_bucket"] == bucket]
        plt.scatter(
            subset["umap1"],
            subset["umap2"],
            s=18,
            alpha=0.55,
            label=bucket,
            color=colors(idx % 10),
        )

    plt.xlabel("UMAP1")
    plt.ylabel("UMAP2")
    plt.title("Steam Game Positioning Map (Taxonomy UMAP)")
    plt.legend(title="owners_bucket", fontsize=8, title_fontsize=9, loc="best")
    plt.grid(alpha=0.15)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UMAP on taxonomy_matrix.csv and export coordinates + plot.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Input taxonomy matrix CSV path.",
    )
    parser.add_argument(
        "--coords-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_umap_coords.csv"),
        help="Output CSV path for UMAP coordinates.",
    )
    parser.add_argument(
        "--plot-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_umap_scatter.png"),
        help="Output PNG path for UMAP scatter plot.",
    )
    parser.add_argument("--n-neighbors", type=int, default=30, help="UMAP n_neighbors.")
    parser.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist.")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    df = load_matrix(Path(args.input))
    coords_df = run_umap(
        df,
        n_neighbors=args.n_neighbors,
        min_dist=args.min_dist,
        random_state=args.random_state,
    )
    coords_out_path = Path(args.coords_out)
    coords_out_path.parent.mkdir(parents=True, exist_ok=True)
    coords_df.to_csv(coords_out_path, index=False, encoding="utf-8-sig")
    plot_scatter(Path(args.plot_out), coords_df)

    print(f"Rows: {len(df)}")
    print(f"Coords: {args.coords_out}")
    print(f"Plot: {args.plot_out}")
    print(f"n_neighbors: {args.n_neighbors}")
    print(f"min_dist: {args.min_dist}")


if __name__ == "__main__":
    main()
