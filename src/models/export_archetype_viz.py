"""
export_archetype_viz.py

Project the fitted K-Means archetype clusters down to 2D via PCA (on the
same standardized feature space the model was trained on) and write a
static JSON file for the frontend About page's cluster scatter plot.

This is a visualization-only artifact — it does not affect the trained
model or the archetype assignments in player_archetypes.parquet.

Usage
-----
    python -m src.models.export_archetype_viz
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.decomposition import PCA

from src.models.player_archetypes import STAT_COLS, PlayerArchetypeModel


def main() -> None:
    archetypes_path = Path("data/processed/player_archetypes.parquet")
    model_path = Path("data/models/player_archetypes_kmeans.pkl")
    names_path = Path("data/processed/player_names.json")
    output_path = Path("frontend/src/data/archetype_clusters.json")

    archetypes_df = pd.read_parquet(archetypes_path)
    model = PlayerArchetypeModel.load(model_path)
    names = json.loads(names_path.read_text())

    X = archetypes_df[STAT_COLS].to_numpy(dtype=float)
    X_scaled = model._scaler.transform(X)

    # Fit PCA on the eligible (clustered) players only, then project everyone
    # (including "unknown" low-sample players) through the same transform.
    eligible_mask = archetypes_df["archetype"] != "unknown"
    pca = PCA(n_components=2, random_state=42)
    pca.fit(X_scaled[eligible_mask.to_numpy()])
    coords = pca.transform(X_scaled)

    points = [
        {
            "id": row.player_id,
            "name": names.get(row.player_id, row.player_id[:8]),
            "archetype": row.archetype,
            "x": round(float(coords[i, 0]), 3),
            "y": round(float(coords[i, 1]), 3),
            "n_games": int(row.n_games),
        }
        for i, row in enumerate(archetypes_df.itertuples(index=False))
    ]

    output = {
        "points": points,
        "explained_variance": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "silhouette": round(
            model.silhouette_score(pd.read_parquet("data/processed/player_stats.parquet")), 4
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(points)} points → {output_path}")
    print(f"Explained variance: PC1={output['explained_variance'][0]:.1%} "
          f"PC2={output['explained_variance'][1]:.1%}")
    print(f"Silhouette: {output['silhouette']}")


if __name__ == "__main__":
    main()
