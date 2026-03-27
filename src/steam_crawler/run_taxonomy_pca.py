import argparse
import csv
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from paths import FIGURES_DIR, PROCESSED_DATA_DIR


META_COLUMNS = ["appid", "name", "owners_bucket", "price_usd", "is_free"]
FEATURE_PREFIX = "tax::"


def load_matrix(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def select_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    feature_cols = [col for col in df.columns if col.startswith(FEATURE_PREFIX)]
    return df[feature_cols].copy(), feature_cols


def run_pca(df: pd.DataFrame, n_components: int) -> Tuple[pd.DataFrame, PCA, List[str]]:
    features, feature_cols = select_features(df)
    imputer = SimpleImputer(strategy="constant", fill_value=0.0)
    X = imputer.fit_transform(features)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=n_components, random_state=42)
    coords = pca.fit_transform(X_scaled)

    out = df[META_COLUMNS].copy()
    out["pc1"] = coords[:, 0]
    out["pc2"] = coords[:, 1]
    if n_components >= 3:
        out["pc3"] = coords[:, 2]
    return out, pca, feature_cols


def write_coords(path: Path, coords_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    coords_df.to_csv(path, index=False, encoding="utf-8-sig")


def plot_scatter(path: Path, coords_df: pd.DataFrame, pca: PCA) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bucket_order = sorted(coords_df["owners_bucket"].dropna().unique().tolist())
    colors = plt.get_cmap("tab10")

    plt.figure(figsize=(12, 8))
    for idx, bucket in enumerate(bucket_order):
        subset = coords_df[coords_df["owners_bucket"] == bucket]
        plt.scatter(
            subset["pc1"],
            subset["pc2"],
            s=18,
            alpha=0.55,
            label=bucket,
            color=colors(idx % 10),
        )

    plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.2f}% var)")
    plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.2f}% var)")
    plt.title("Steam Game Positioning Map (Taxonomy PCA)")
    plt.legend(title="owners_bucket", fontsize=8, title_fontsize=9, loc="best")
    plt.grid(alpha=0.15)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_scatter_3d(path: Path, coords_df: pd.DataFrame, pca: PCA) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bucket_order = sorted(coords_df["owners_bucket"].dropna().unique().tolist())
    colors = plt.get_cmap("tab10")

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection="3d")
    for idx, bucket in enumerate(bucket_order):
        subset = coords_df[coords_df["owners_bucket"] == bucket]
        ax.scatter(
            subset["pc1"],
            subset["pc2"],
            subset["pc3"],
            s=12,
            alpha=0.45,
            label=bucket,
            color=colors(idx % 10),
        )

    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.2f}% var)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.2f}% var)")
    ax.set_zlabel(f"PC3 ({pca.explained_variance_ratio_[2] * 100:.2f}% var)")
    ax.set_title("Steam Game Positioning Map (Taxonomy PCA 3D)")
    ax.legend(title="owners_bucket", fontsize=8, title_fontsize=9, loc="best")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def write_loadings(path: Path, pca: PCA, feature_cols: List[str], top_n: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for comp_idx, component in enumerate(pca.components_, start=1):
        pairs = sorted(
            zip(feature_cols, component),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:top_n]
        for feature, weight in pairs:
            rows.append(
                {
                    "component": f"PC{comp_idx}",
                    "feature": feature,
                    "loading": weight,
                }
            )

    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["component", "feature", "loading"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PCA on taxonomy_matrix.csv and export coordinates + plot.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Input taxonomy matrix CSV path.",
    )
    parser.add_argument(
        "--coords-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_pca_coords.csv"),
        help="Output CSV path for PCA coordinates.",
    )
    parser.add_argument(
        "--plot-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_pca_scatter.png"),
        help="Output PNG path for PCA scatter plot.",
    )
    parser.add_argument(
        "--loadings-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_pca_loadings.csv"),
        help="Output CSV path for top PCA loadings.",
    )
    parser.add_argument(
        "--components",
        type=int,
        default=3,
        help="Number of PCA components to compute.",
    )
    parser.add_argument(
        "--plot3d-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_pca_scatter_3d.png"),
        help="Output PNG path for 3D PCA scatter plot.",
    )
    args = parser.parse_args()

    df = load_matrix(Path(args.input))
    coords_df, pca, feature_cols = run_pca(df, n_components=args.components)
    write_coords(Path(args.coords_out), coords_df)
    plot_scatter(Path(args.plot_out), coords_df, pca)
    if args.components >= 3:
        plot_scatter_3d(Path(args.plot3d_out), coords_df, pca)
    write_loadings(Path(args.loadings_out), pca, feature_cols)

    print(f"Rows: {len(df)}")
    print(f"Features: {len(feature_cols)}")
    print(f"Explained variance PC1: {pca.explained_variance_ratio_[0]:.6f}")
    print(f"Explained variance PC2: {pca.explained_variance_ratio_[1]:.6f}")
    if args.components >= 3:
        print(f"Explained variance PC3: {pca.explained_variance_ratio_[2]:.6f}")
    print(f"Coords: {args.coords_out}")
    print(f"Plot: {args.plot_out}")
    if args.components >= 3:
        print(f"Plot3D: {args.plot3d_out}")
    print(f"Loadings: {args.loadings_out}")


if __name__ == "__main__":
    main()
