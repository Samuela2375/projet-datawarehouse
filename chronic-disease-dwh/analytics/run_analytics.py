# =============================================================================
# analytics/run_analytics.py
# Point d'entrée principal — exécute toutes les analyses et exporte les CSV
# Usage : python analytics/run_analytics.py
# =============================================================================

import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

from analytics.utils import run_query, export_results

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QUERIES = [
    {
        "sql":    "analytics/prevalence/top_diseases.sql",
        "export": "data/exports/prevalence/top_diseases.csv",
        "label":  "Top 10 maladies",
    },
    {
        "sql":    "analytics/prevalence/by_state.sql",
        "export": "data/exports/prevalence/by_state.csv",
        "label":  "Prévalence par État",
    },
    {
        "sql":    "analytics/prevalence/by_demographics.sql",
        "export": "data/exports/prevalence/by_demographics.csv",
        "label":  "Prévalence par démographie",
    },
    {
        "sql":    "analytics/forecasting/time_evolution.sql",
        "export": "data/exports/forecasting/time_evolution.csv",
        "label":  "Évolution temporelle",
    },
]

# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv()

    DB_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/chronic_disease_dwh"
    )
    engine = create_engine(DB_URL)

    print("=" * 60)
    print("  Pipeline Analytics — Chronic Disease DWH")
    print("=" * 60)

    # 1. Requêtes SQL
    with engine.connect() as conn:
        for q in QUERIES:
            print(f"\n→ {q['label']}...")
            df = run_query(q["sql"], conn)
            export_results(df, q["export"])

    # 2. Classification K-Means (script dédié)
    print("\n→ Classification des États (K-Means)...")
    from analytics.risk_classification.classify_states import classifier_etats
    classifier_etats(
        engine=engine,
        export_path="data/exports/risk_classification/clusters_etats.csv"
    )

    print("\n" + "=" * 60)
    print("  Toutes les analyses sont terminées.")
    print("  Résultats dans : data/exports/")
    print("=" * 60)