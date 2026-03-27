import argparse
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from paths import FIGURES_DIR, PROCESSED_DATA_DIR


META_COLUMNS = ["appid", "name", "owners_bucket", "price_usd", "is_free"]
FEATURE_PREFIX = "tax::"
COLOR_MAP = {
    "0_20k": "#1f77b4",
    "20k_50k": "#ff7f0e",
    "50k_100k": "#2ca02c",
    "100k_200k": "#d62728",
    "200k_500k": "#9467bd",
    "500k_1m": "#8c564b",
    "1m_2m": "#e377c2",
    "2m_5m": "#7f7f7f",
    "5m_plus": "#bcbd22",
}


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


def build_figure(
    coords_df: pd.DataFrame,
    labeled_df: pd.DataFrame,
    pca: PCA,
    rays: List[Tuple[str, float, float, float, float]],
    sample_points: int,
    arrow_scale: float,
    zoom_percentile: float,
) -> go.Figure:
    plot_df = coords_df.copy()
    if sample_points > 0 and sample_points < len(plot_df):
        plot_df = plot_df.sample(sample_points, random_state=42)

    robust_limit = max(
        float(plot_df["pc1"].abs().quantile(zoom_percentile)),
        float(plot_df["pc2"].abs().quantile(zoom_percentile)),
        float(plot_df["pc3"].abs().quantile(zoom_percentile)),
    )
    axis_limit = robust_limit * 1.15 if robust_limit > 0 else 1.0

    plot_df = plot_df[
        (plot_df["pc1"].abs() <= axis_limit)
        & (plot_df["pc2"].abs() <= axis_limit)
        & (plot_df["pc3"].abs() <= axis_limit)
    ].copy()

    traces = []
    for bucket in sorted(plot_df["owners_bucket"].dropna().unique().tolist()):
        subset = plot_df[plot_df["owners_bucket"] == bucket]
        traces.append(
            go.Scatter3d(
                x=subset["pc1"],
                y=subset["pc2"],
                z=subset["pc3"],
                mode="markers",
                name=bucket,
                marker=dict(size=3.2, opacity=0.35, color=COLOR_MAP.get(bucket, "#999999")),
                text=subset["name"],
                customdata=subset[["appid", "price_usd", "is_free"]],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "appid=%{customdata[0]}<br>"
                    "price_usd=%{customdata[1]}<br>"
                    "is_free=%{customdata[2]}<br>"
                    "pc1=%{x:.2f}<br>"
                    "pc2=%{y:.2f}<br>"
                    "pc3=%{z:.2f}<extra></extra>"
                ),
            )
        )

    if not labeled_df.empty:
        traces.append(
            go.Scatter3d(
                x=labeled_df["pc1"],
                y=labeled_df["pc2"],
                z=labeled_df["pc3"],
                mode="markers+text",
                name="Top-selling games",
                marker=dict(size=5.5, opacity=0.95, color="black", symbol="diamond"),
                text=labeled_df["name"],
                textposition="top center",
                customdata=labeled_df[["appid", "owners_low", "review_count"]],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "appid=%{customdata[0]}<br>"
                    "owners_low=%{customdata[1]}<br>"
                    "review_count=%{customdata[2]}<br>"
                    "pc1=%{x:.2f}<br>"
                    "pc2=%{y:.2f}<br>"
                    "pc3=%{z:.2f}<extra></extra>"
                ),
            )
        )

    traces.append(
        go.Scatter3d(
            x=[0], y=[0], z=[0],
            mode="markers+text",
            name="Origin",
            marker=dict(size=7, color="black"),
            text=["Origin"],
            textposition="top center",
            hoverinfo="skip",
        )
    )

    axis_lines = [
        ([-axis_limit, axis_limit], [0, 0], [0, 0], "x-axis"),
        ([0, 0], [-axis_limit, axis_limit], [0, 0], "y-axis"),
        ([0, 0], [0, 0], [-axis_limit, axis_limit], "z-axis"),
    ]
    for xs, ys, zs, label in axis_lines:
        traces.append(
            go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode="lines",
                name=label,
                line=dict(color="rgba(100,100,100,0.6)", width=3),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    for feature, x, y, z, _ in rays:
        dx = x * axis_limit * arrow_scale
        dy = y * axis_limit * arrow_scale
        dz = z * axis_limit * arrow_scale
        traces.append(
            go.Scatter3d(
                x=[0, dx],
                y=[0, dy],
                z=[0, dz],
                mode="lines+text",
                name=shorten_feature_name(feature),
                line=dict(color="firebrick", width=5),
                text=["", shorten_feature_name(feature)],
                textposition="top center",
                hovertemplate=f"{feature}<extra></extra>",
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title="Steam Positioning 3D PCA Biplot (Interactive)",
        scene=dict(
            xaxis=dict(title=f"PC1 ({pca.explained_variance_ratio_[0] * 100:.2f}% var)", range=[-axis_limit, axis_limit]),
            yaxis=dict(title=f"PC2 ({pca.explained_variance_ratio_[1] * 100:.2f}% var)", range=[-axis_limit, axis_limit]),
            zaxis=dict(title=f"PC3 ({pca.explained_variance_ratio_[2] * 100:.2f}% var)", range=[-axis_limit, axis_limit]),
            aspectmode="cube",
        ),
        legend=dict(itemsizing="constant"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def load_top_games(clean_games_path: Path, top_n: int) -> pd.DataFrame:
    clean = pd.read_csv(clean_games_path, encoding="utf-8-sig")
    clean["owners_low"] = pd.to_numeric(clean.get("owners_low"), errors="coerce").fillna(0)
    clean["review_count"] = pd.to_numeric(clean.get("review_count"), errors="coerce").fillna(0)
    labeled = (
        clean.sort_values(["owners_low", "review_count"], ascending=[False, False])
        .drop_duplicates(subset=["appid"])
        .head(top_n)
        .copy()
    )
    return labeled[["appid", "name", "owners_low", "review_count"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an interactive 3D PCA biplot HTML.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PROCESSED_DATA_DIR / "taxonomy_matrix.csv"),
        help="Input taxonomy matrix CSV path.",
    )
    parser.add_argument(
        "--html-out",
        type=str,
        default=str(FIGURES_DIR / "taxonomy_pca_biplot_3d.html"),
        help="Output HTML path.",
    )
    parser.add_argument("--top-n-rays", type=int, default=10, help="Number of rays to draw.")
    parser.add_argument("--sample-points", type=int, default=1800, help="How many game points to draw.")
    parser.add_argument("--arrow-scale", type=float, default=0.95, help="Scale factor for feature rays.")
    parser.add_argument("--zoom-percentile", type=float, default=0.90, help="Percentile-based zoom cutoff.")
    parser.add_argument(
        "--clean-games",
        type=str,
        default=str(PROCESSED_DATA_DIR / "clean_games.csv"),
        help="Path to clean_games.csv for top-selling labels.",
    )
    parser.add_argument("--top-n-games", type=int, default=15, help="How many top-selling games to label.")
    args = parser.parse_args()

    df = load_matrix(Path(args.input))
    coords_df, pca, feature_cols = fit_pca(df, n_components=3)
    rays = top_feature_vectors(pca, feature_cols, args.top_n_rays)
    top_games = load_top_games(Path(args.clean_games), args.top_n_games)
    labeled_df = coords_df.merge(top_games, on=["appid", "name"], how="inner")
    fig = build_figure(
        coords_df=coords_df,
        labeled_df=labeled_df,
        pca=pca,
        rays=rays,
        sample_points=args.sample_points,
        arrow_scale=args.arrow_scale,
        zoom_percentile=args.zoom_percentile,
    )
    html_out_path = Path(args.html_out)
    html_out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(html_out_path, include_plotlyjs="cdn")

    print(f"Rows: {len(df)}")
    print(f"Rays drawn: {len(rays)}")
    print(f"HTML: {args.html_out}")


if __name__ == "__main__":
    main()
