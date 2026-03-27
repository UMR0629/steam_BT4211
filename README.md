# Steam Game Crawler

This project collects Steam game metadata from two more stable data sources:

1. `SteamSpy API`
2. `Steam Store API` (`/api/appdetails`)

It avoids scraping and parsing the Steam store HTML pages directly.

## Project Layout

```text
steam_crawler/
├─ src/steam_crawler/          # Python scripts
├─ data/raw/                   # Crawled JSON/CSV files
├─ data/processed/             # Processed tables, mappings, coordinates, and metadata
├─ data/figures/               # PNG/HTML visual outputs
├─ README.md
├─ requirements.txt
└─ steam_crawler_colab.ipynb
```

## What This Project Does

The repository includes a small end-to-end workflow for Steam game market analysis:

- Crawl app data from SteamSpy and the Steam Store API
- Export normalized results to JSON and CSV
- Draw a more balanced stratified sample of games
- Clean and featurize the crawled data for positioning analysis
- Build tag matrices and taxonomy-level feature matrices
- Run PCA and UMAP for visualization
- Generate annotated plots for content clusters and well-known games

## Installation

Base dependency for the crawler:

```bash
cd D:\pythonProject\steam_crawler
pip install -r requirements.txt
```

If you are using a virtual environment:

```bash
cd D:\pythonProject\steam_crawler
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` includes the crawler and analysis dependencies used by the repository:

- `requests`
- `pandas`
- `matplotlib`
- `scikit-learn`
- `umap-learn`
- `plotly`

## Running in Google Colab

The project can run in Colab, and it is much smoother now than a raw script-only workflow.

Recommended setup:

1. Put the whole `steam_crawler` folder in Google Drive.
2. Open [steam_crawler_colab.ipynb](d:\pythonProject\steam_crawler\steam_crawler_colab.ipynb) in Colab.
3. Update the `PROJECT_DIR` cell so it points to your Drive copy of the folder.
4. Run the notebook top to bottom.

The notebook is designed as a step-by-step tutorial and includes:

- dependency installation
- project-path validation
- a choice between reusing an existing sample or crawling a fresh sample
- preprocessing
- taxonomy aggregation
- PCA and UMAP generation
- cluster and top-game labeling
- optional interactive 3D PCA export
- zipping the final outputs for sharing

For most team use cases in Colab, reusing files such as `data/raw/sample_100.json`, `data/raw/sample_2000.json`, or `data/raw/sample_5000.json` is more reliable than live crawling during a notebook session.

## Main Crawler

The main entry point is:

```bash
python src/steam_crawler/crawler.py
```

### Crawl specific appids

```bash
python src/steam_crawler/crawler.py --appids 730,570,1091500 --json-out data/raw/out.json --csv-out data/raw/out.csv
```

### Crawl the first N appids from SteamSpy `all`

```bash
python src/steam_crawler/crawler.py --top-n-from-steamspy-all 100 --json-out data/raw/out.json --csv-out data/raw/out.csv
```

### Draw a stratified sample

```bash
python src/steam_crawler/crawler.py --sample-size 500 --sample-seed 42 --steamspy-catalog-pages 5 --steamspy-page-delay 15 --delay 1.0 --progress-every 50 --json-out data/raw/out.json --csv-out data/raw/out.csv
```

## Sampling Strategy

If you plan to do positioning analysis or dimensionality reduction later, `--sample-size` is usually better than taking the first N appids.

The stratified sampler groups games by:

- `owners_range`
- `price`

It then samples round-robin across those buckets to reduce bias toward only the most popular, high-owner games.

Notes:

- `SteamSpy request=all` is paginated.
- If you only load page `1` of the catalog pool, the sample will be biased toward higher-owner games.
- To make the sample more representative, increase `--steamspy-catalog-pages` to `3`, `5`, or more.
- Each extra page adds time, and the delay between pages is controlled by `--steamspy-page-delay` with a default of `15` seconds.

## Output Schema

### Fields mainly sourced from SteamSpy

- `appid`
- `name`
- `owners_range`
- `positive`
- `negative`
- `ccu`
- `average_forever`
- `median_forever`
- `average_2weeks`
- `median_2weeks`
- `languages`
- `tags`

### Fields mainly sourced from the Steam Store API

- `type`
- `is_free`
- `price_cents`
- `initial_price_cents`
- `short_description`
- `about_the_game`
- `detailed_description`
- `release_date`
- `coming_soon`
- `supported_languages`
- `developers`
- `publishers`
- `genres`
- `categories`
- `platforms`
- `recommendations_total`
- `metacritic_score`
- `website`
- `header_image`

## Progress Logging

By default, progress is printed every `50` games:

```text
[50/500]  10.00% last_appid=620 name=Portal 2 steamspy=ok store_api=ok
```

You can change the interval:

```bash
python src/steam_crawler/crawler.py --sample-size 500 --progress-every 20
```

## Recommended Commands

Get a relatively balanced sample of `100` games:

```bash
python src/steam_crawler/crawler.py --sample-size 100 --steamspy-catalog-pages 5 --steamspy-page-delay 15 --delay 1.0 --progress-every 25 --json-out data/raw/sample_100.json --csv-out data/raw/sample_100.csv
```

Get a larger sample for downstream analysis:

```bash
python src/steam_crawler/crawler.py --sample-size 1000 --steamspy-catalog-pages 10 --steamspy-page-delay 15 --delay 1.0 --progress-every 50 --json-out data/raw/sample_1000.json --csv-out data/raw/sample_1000.csv
```

## Notes

- `price_cents` and `initial_price_cents` are stored in cents.
- `tags` come directly from `SteamSpy appdetails.tags`.
- `about_the_game` and `detailed_description` are stripped of HTML for easier text analysis.
- The Steam Store API endpoint used here is publicly accessible, but it should be treated as an unofficial integration point. If Valve changes the response structure, this script may need small updates.

## Positioning Preprocessing

If you want to convert a crawled JSON file into cleaner analysis-ready data, run:

```bash
python src/steam_crawler/preprocess_positioning.py --input data/raw/sample_5000.json --out-dir data/processed
```

This script:

- Keeps only rows where `type=game` by default
- Parses `owners_range` into lower bound, upper bound, and `owners_bucket`
- Computes `review_count` and `positive_ratio`
- Computes `release_age_days`
- Computes `log_price`, `log_ccu`, `log_average_forever`, and `log_recommendations_total`
- Normalizes tag weights using `log1p`
- Drops generic tags from the filtered tag profile
- Builds tag statistics and a per-game tag matrix

Output files:

- `data/processed/clean_games.csv`
- `data/processed/tag_stats.csv`
- `data/processed/tag_matrix.csv`
- `data/processed/metadata.json`

In practice:

- `clean_games.csv` is the most convenient table for business-side analysis
- `tag_stats.csv` is useful when designing a tag taxonomy
- `tag_matrix.csv` is useful for positioning analysis, clustering, PCA, and UMAP

## Taxonomy Aggregation

After preparing `tag_matrix.csv`, you can merge detailed tags into higher-level taxonomy buckets with:

```bash
python src/steam_crawler/aggregate_taxonomy_matrix.py --tag-matrix data/processed/tag_matrix.csv --mapping data/processed/taxonomy_mapping.csv --out data/processed/taxonomy_matrix.csv --feature-out data/processed/taxonomy_features.csv
```

This script uses `taxonomy_mapping.csv` to convert `tag::<tag>` columns into `tax::<dimension>::<bucket>` features.

Output files:

- `data/processed/taxonomy_matrix.csv`
- `data/processed/taxonomy_features.csv`

## PCA Workflow

Run PCA on the taxonomy matrix:

```bash
python src/steam_crawler/run_taxonomy_pca.py --input data/processed/taxonomy_matrix.csv
```

Default outputs:

- `data/processed/taxonomy_pca_coords.csv`
- `data/processed/taxonomy_pca_loadings.csv`
- `data/figures/taxonomy_pca_scatter.png`
- `data/figures/taxonomy_pca_scatter_3d.png`

The script standardizes taxonomy features, fills missing values with zero, and exports PCA coordinates plus the strongest feature loadings for each principal component.

## UMAP Workflow

Run UMAP on the taxonomy matrix:

```bash
python src/steam_crawler/run_taxonomy_umap.py --input data/processed/taxonomy_matrix.csv
```

Default outputs:

- `data/processed/taxonomy_umap_coords.csv`
- `data/figures/taxonomy_umap_scatter.png`

## Annotated UMAP Visualizations

### Label content clusters

```bash
python src/steam_crawler/annotate_taxonomy_umap.py --umap-coords data/processed/taxonomy_umap_coords.csv --taxonomy-matrix data/processed/taxonomy_matrix.csv
```

Default outputs:

- `data/figures/taxonomy_umap_annotated.png`
- `data/processed/taxonomy_cluster_summary.csv`
- `data/processed/taxonomy_umap_clusters.csv`

This script runs KMeans on the taxonomy features and overlays cluster names on the UMAP map.

### Label top or famous games

```bash
python src/steam_crawler/annotate_famous_games_umap.py --coords data/processed/taxonomy_umap_coords.csv --clean-games data/processed/clean_games.csv --top-n 20
```

Default outputs:

- `data/figures/taxonomy_umap_top_games.png`
- `data/processed/top_games_labels.csv`

The labeled games are selected by sorting on `owners_low` and `review_count`.

## Typical End-to-End Flow

```bash
python src/steam_crawler/crawler.py --sample-size 5000 --steamspy-catalog-pages 10 --steamspy-page-delay 15 --delay 1.0 --json-out data/raw/sample_5000.json --csv-out data/raw/sample_5000.csv
python src/steam_crawler/preprocess_positioning.py --input data/raw/sample_5000.json --out-dir data/processed
python src/steam_crawler/aggregate_taxonomy_matrix.py
python src/steam_crawler/run_taxonomy_pca.py
python src/steam_crawler/run_taxonomy_umap.py
python src/steam_crawler/annotate_taxonomy_umap.py
python src/steam_crawler/annotate_famous_games_umap.py
```

## Typical Colab Flow

If your teammates are using Colab, the recommended flow is:

1. Copy the `steam_crawler` folder to Google Drive.
2. Open [steam_crawler_colab.ipynb](d:\pythonProject\steam_crawler\steam_crawler_colab.ipynb).
3. Point `PROJECT_DIR` at the Drive folder.
4. Prefer an existing sample JSON unless you specifically need a fresh crawl.
5. Run the notebook cells in order and use the generated zip archive at the end for sharing results.

## Repository Files

- `src/steam_crawler/crawler.py`: main data collection script
- `src/steam_crawler/preprocess_positioning.py`: cleaning and feature engineering for positioning analysis
- `src/steam_crawler/aggregate_taxonomy_matrix.py`: merges tag-level features into taxonomy-level features
- `src/steam_crawler/run_taxonomy_pca.py`: PCA coordinates and plots
- `src/steam_crawler/run_taxonomy_umap.py`: UMAP coordinates and plots
- `src/steam_crawler/annotate_taxonomy_umap.py`: cluster-labeled UMAP visualization
- `src/steam_crawler/annotate_famous_games_umap.py`: top-game-labeled UMAP visualization
- `steam_crawler_colab.ipynb`: Colab-friendly step-by-step notebook for the full workflow
