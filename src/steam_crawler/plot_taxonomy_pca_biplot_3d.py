import argparse
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


def fit_pca(df: pd.DataFrame, n_components: int = 3) -> Tuple[pd.DataFrame, PCA, List[str]]:
    feature_cols = [col for col in df.columns if col.startswith(FEATURE_PREFIX)]
    X = df[feature_cols].copy()
    X = SimpleImputer(strategy="constant", fill_value=0.0).fit_transform(X)
    X = StandardScaler().fit_transform(X)

    pca = PCA(n_components=n_components, random_state=42)
    coords = pca.fit_transform(X)

    out = df[META_COLUMNS].copy()
    out["pc1"] = coords[:, 0]
    out["pc2"] = coords[:, 1]
    out["pc3"] = coords[:, 2]
    return out, pca, feature_cols


def top_feature_vectors(
    pca: PCA,
    feature_cols: List[str],
    top_n: int,
) -> List[Tuple[str, float, float, float, float]]:
    rows = []
    for idx, feature in enumerate(feature_cols):
        x = float(pca.components_[0, idx])
        y = float(pca.components_[1, idx])
        z = float(pca.components_[2, idx])
        magnitude = (x * x + y * y + z * z) ** 0.5
        rows.append((feature, x, y, z, magnitude))
    rows.sort(key=lambda item: item[4], reverse=True)
    return rows[:top_n]


def shorten_feature_name(name: str) -> str:
    if name.startswith("tax::"):
        parts = name.split("::", 2)
        if len(parts) == 3:
            return parts[2]
    return name


def plot_biplot_3d(
    coords_df: pd.DataFrame,
    feature_vectors: List[Tuple[str, float, float, float, float]],
    pca: PCA,
    out_path: Path,
    sample_points: int,
    arrow_scale: float,
    zoom_percentile: float,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bucket_order = sorted(coords_df["owners_bucket"].dropna().unique().tolist())
    colors = plt.get_cmap("tab10")

    plot_df = coords_df.copy()
    if sample_points > 0 and sample_points < len(plot_df):
        plot_df = plot_df.sample(sample_points, random_state=42)

    abs_pc1 = plot_df["pc1"].abs()
    abs_pc2 = plot_df["pc2"].abs()
    abs_pc3 = plot_df["pc3"].abs()
    robust_limit = max(
        float(abs_pc1.quantile(zoom_percentile)),
        float(abs_pc2.quantile(zoom_percentile)),
        float(abs_pc3.quantile(zoom_percentile)),
    )
    full_limit = max(
        float(abs_pc1.max()),
        float(abs_pc2.max()),
        float(abs_pc3.max()),
    )
    max_point = robust_limit if robust_limit > 0 else full_limit
    axis_limit = max_point * 1.15 if max_point > 0 else 1.0

    fig = plt.figure(figsize=(13, 10))
    ax = fig.add_subplot(111, projection="3d")

    # Draw symmetric axes through the origin so the origin is visually obvious.
    ax.plot([-axis_limit, axis_limit], [0, 0], [0, 0], color="#666666", linewidth=1.0, alpha=0.7)
    ax.plot([0, 0], [-axis_limit, axis_limit], [0, 0], color="#666666", linewidth=1.0, alpha=0.7)
    ax.plot([0, 0], [0, 0], [-axis_limit, axis_limit], color="#666666", linewidth=1.0, alpha=0.7)

    for idx, bucket in enumerate(bucket_order):
        subset = plot_df[
            (plot_df["owners_bucket"] == bucket)
            & (plot_df["pc1"].abs() <= axis_limit)
            & (plot_df["pc2"].abs() <= axis_limit)
            & (plot_df["pc3"].abs() <= axis_limit)
        ]
        ax.scatter(
            subset["pc1"],
            subset["pc2"],
            subset["pc3"],
            s=8,
            alpha=0.10,
            color=colors(idx % 10),
            label=bucket,
        )

    ax.scatter([0], [0], [0], s=180, color="black", marker="o", edgecolors="white", linewidths=0.8)
    ax.text(0, 0, 0, "Origin (0,0,0)", fontsize=10, ha="left", va="bottom", color="black")

    for feature, x, y, z, _ in feature_vectors:
        dx = x * max_point * arrow_scale
        dy = y * max_point * arrow_scale
        dz = z * max_point * arrow_scale
        ax.quiver(
            0, 0, 0,
            dx, dy, dz,
            color="#c0392b",
            linewidth=1.4,
            arrow_length_ratio=0.08,
        )
        ax.text(
            dx * 1.08,
            dy * 1.08,
            dz * 1.08,
            shorten_feature_name(feature),
            color="#922b21",
            fontsize=8,
            ha="center",
            va="center",
        )

    ax.set_xlim(-axis_limit, axis_limit)
    ax.set_ylim(-axis_limit, axis_limit)
    ax.set_zlim(-axis_limit, axis_limit)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.2f}% var)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.2f}% var)")
    ax.set_zlabel(f"PC3 ({pca.explained_variance_ratio_[2] * 100:.2f}% var)")
    ax.set_title("Steam Positioning 3D PCA Biplot")
    ax.legend(title="owners_bucket", fontsize=8, title_fontsize=9, loc="best")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a 3D PCA biplot with taxonomy rays.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Input taxonomy matrix CSV path.",
    )
    parser.add_argument(
        "--plot-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_pca_biplot_3d.png"),
        help="Output PNG path.",
    )
    parser.add_argument(
        "--coords-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_pca_biplot_coords.csv"),
        help="Output CSV path for 3D PCA coordinates.",
    )
    parser.add_argument(
        "--rays-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_pca_biplot_rays.csv"),
        help="Output CSV path for selected rays.",
    )
    parser.add_argument("--top-n-rays", type=int, default=15, help="Number of feature rays to draw.")
    parser.add_argument("--sample-points", type=int, default=2500, help="How many game points to draw.")
    parser.add_argument("--arrow-scale", type=float, default=0.55, help="Scale factor for feature rays.")
    parser.add_argument(
        "--zoom-percentile",
        type=float,
        default=0.95,
        help="Use this percentile of absolute PCA coordinates to set symmetric axis limits for a zoomed-in view.",
    )
    args = parser.parse_args()

    df = load_matrix(Path(args.input))
    coords_df, pca, feature_cols = fit_pca(df, n_components=3)
    rays = top_feature_vectors(pca, feature_cols, args.top_n_rays)

    coords_out_path = Path(args.coords_out)
    rays_out_path = Path(args.rays_out)
    coords_out_path.parent.mkdir(parents=True, exist_ok=True)
    rays_out_path.parent.mkdir(parents=True, exist_ok=True)
    coords_df.to_csv(coords_out_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [{"feature": f, "pc1_loading": x, "pc2_loading": y, "pc3_loading": z, "magnitude": m} for f, x, y, z, m in rays]
    ).to_csv(rays_out_path, index=False, encoding="utf-8-sig")
    plot_biplot_3d(
        coords_df=coords_df,
        feature_vectors=rays,
        pca=pca,
        out_path=Path(args.plot_out),
        sample_points=args.sample_points,
        arrow_scale=args.arrow_scale,
        zoom_percentile=args.zoom_percentile,
    )

    print(f"Rows: {len(df)}")
    print(f"Rays drawn: {len(rays)}")
    print(f"Coords: {args.coords_out}")
    print(f"Rays: {args.rays_out}")
    print(f"Plot: {args.plot_out}")


if __name__ == "__main__":
    main()
