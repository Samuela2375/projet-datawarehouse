# =============================================================================
# analytics/run_analytics.py
# Point d'entrée principal — exécute toutes les analyses et exporte les CSV
# Usage : python -m analytics.run_analytics
# =============================================================================

import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from dotenv import load_dotenv
from analytics.utils import run_query, export_results

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

user     = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "changeme")
host     = os.getenv("DB_HOST", "localhost")
port     = os.getenv("DB_PORT", "5432")
dbname   = os.getenv("DB_NAME", "chronic_disease_dwh")

DB_URL = f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{dbname}"

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

    # 2. Classification K-Means
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