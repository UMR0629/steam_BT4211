import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from paths import FIGURES_DIR, PROCESSED_DATA_DIR


FEATURE_PREFIX = "tax::"
DEFAULT_CLUSTER_NAMES: Dict[int, str] = {
    0: "FPS / Military / Co-op",
    1: "Arcade / Platformer / Casual",
    2: "Survival Horror",
    3: "Turn-Based Strategy",
    4: "Sandbox / Building / Management",
    5: "Visual Novel / Anime Narrative",
    6: "Roguelike / Dungeon Loop",
    7: "Third-Person Action RPG",
}


def load_inputs(
    umap_path: Path,
    matrix_path: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    coords = pd.read_csv(umap_path, encoding="utf-8-sig")
    matrix = pd.read_csv(matrix_path, encoding="utf-8-sig")
    feature_cols = [col for col in matrix.columns if col.startswith(FEATURE_PREFIX)]
    return coords, matrix, feature_cols


def cluster_games(matrix: pd.DataFrame, feature_cols: List[str], n_clusters: int) -> pd.Series:
    X = matrix[feature_cols]
    X = SimpleImputer(strategy="constant", fill_value=0.0).fit_transform(X)
    X = StandardScaler().fit_transform(X)
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=20).fit_predict(X)
    return pd.Series(labels, index=matrix.index, name="cluster")


def make_cluster_summary(
    coords: pd.DataFrame,
    cluster_names: Dict[int, str],
) -> pd.DataFrame:
    grouped = coords.groupby("cluster").agg(
        umap1=("umap1", "mean"),
        umap2=("umap2", "mean"),
        size=("cluster", "size"),
    )
    grouped = grouped.reset_index()
    grouped["cluster_name"] = grouped["cluster"].map(cluster_names).fillna(grouped["cluster"].astype(str))
    return grouped


def draw_plot(coords: pd.DataFrame, summary: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(13, 9))
    plt.scatter(coords["umap1"], coords["umap2"], s=12, alpha=0.2, color="#7f8c8d")

    palette = plt.get_cmap("tab10")
    for idx, row in summary.iterrows():
        cluster_id = int(row["cluster"])
        cluster_points = coords[coords["cluster"] == cluster_id]
        plt.scatter(
            cluster_points["umap1"],
            cluster_points["umap2"],
            s=14,
            alpha=0.35,
            color=palette(cluster_id % 10),
        )
        plt.scatter(
            row["umap1"],
            row["umap2"],
            s=220,
            marker="X",
            color=palette(cluster_id % 10),
            edgecolors="black",
            linewidths=0.8,
        )
        plt.text(
            row["umap1"],
            row["umap2"],
            f"{row['cluster_name']}\n(n={int(row['size'])})",
            fontsize=9,
            ha="center",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.82, "edgecolor": "#444"},
        )

    plt.title("Steam Positioning Map (UMAP with Content Clusters)")
    plt.xlabel("UMAP1")
    plt.ylabel("UMAP2")
    plt.grid(alpha=0.12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate UMAP plot with content clusters.")
    parser.add_argument(
        "--umap-coords",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_umap_coords.csv"),
        help="Path to taxonomy UMAP coordinates CSV.",
    )
    parser.add_argument(
        "--taxonomy-matrix",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Path to taxonomy feature matrix CSV.",
    )
    parser.add_argument(
        "--plot-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_umap_annotated.png"),
        help="Path to annotated UMAP plot.",
    )
    parser.add_argument(
        "--summary-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_cluster_summary.csv"),
        help="Path to cluster summary CSV.",
    )
    parser.add_argument(
        "--games-out",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_umap_clusters.csv"),
        help="Path to per-game cluster assignment CSV.",
    )
    parser.add_argument("--n-clusters", type=int, default=8, help="Number of KMeans clusters.")
    args = parser.parse_args()

    coords, matrix, feature_cols = load_inputs(Path(args.umap_coords), Path(args.taxonomy_matrix))
    coords = coords.copy()
    coords["cluster"] = cluster_games(matrix, feature_cols, args.n_clusters)
    cluster_names = DEFAULT_CLUSTER_NAMES.copy()
    summary = make_cluster_summary(coords, cluster_names)
    draw_plot(coords, summary, Path(args.plot_out))

    coords["cluster_name"] = coords["cluster"].map(cluster_names).fillna(coords["cluster"].astype(str))
    games_out_path = Path(args.games_out)
    summary_out_path = Path(args.summary_out)
    games_out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_out_path.parent.mkdir(parents=True, exist_ok=True)
    coords.to_csv(games_out_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_out_path, index=False, encoding="utf-8-sig")

    print(f"Rows: {len(coords)}")
    print(f"Clusters: {args.n_clusters}")
    print(f"Plot: {args.plot_out}")
    print(f"Summary: {args.summary_out}")
    print(f"Games: {args.games_out}")


if __name__ == "__main__":
    main()
