# =============================================================================
# analytics/risk_classification/classify_states.py
# Classification des États par profil épidémiologique (K-Means)
# - Utilise FACT_RISK_FACTOR (risk_score par État et par maladie)
# - Assigne un cluster à 100% des États (3 à 5 clusters)
# - Exporte le résultat en CSV dans data/exports/risk_classification/
# =============================================================================

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Utilitaires partagés
# ---------------------------------------------------------------------------

def run_query(query_path: str, conn) -> pd.DataFrame:
    """Lit un fichier .sql et exécute la requête. Retourne un DataFrame."""
    with open(query_path, "r", encoding="utf-8") as f:
        sql = f.read()
    return pd.read_sql(text(sql), conn)


def export_results(df: pd.DataFrame, path: str) -> None:
    """Exporte un DataFrame en CSV dans le dossier cible (crée le dossier si besoin)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  ✓ Exporté → {path}  ({len(df)} lignes)")


# ---------------------------------------------------------------------------
# Chargement des données depuis FACT_RISK_FACTOR
# ---------------------------------------------------------------------------

def load_risk_matrix(engine) -> pd.DataFrame:
    """
    Construit une matrice États × Maladies à partir de FACT_RISK_FACTOR.
    Chaque cellule = risk_score moyen sur toutes les années disponibles.
    Retourne un DataFrame avec location_abbr en index et topic_name en colonnes.
    """
    sql = """
        SELECT
            dl.location_abbr,
            dl.location_desc,
            dt.topic_name,
            AVG(rf.risk_score) AS risk_score_moyen
        FROM FACT_RISK_FACTOR rf
        JOIN DIM_LOCATION dl ON rf.location_id = dl.location_id
        JOIN DIM_TOPIC    dt ON rf.topic_id    = dt.topic_id
        WHERE rf.risk_score IS NOT NULL
        GROUP BY dl.location_abbr, dl.location_desc, dt.topic_name
        ORDER BY dl.location_abbr, dt.topic_name
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)

    # Pivot : États en lignes, maladies en colonnes
    matrix = df.pivot_table(
        index=["location_abbr", "location_desc"],
        columns="topic_name",
        values="risk_score_moyen",
        aggfunc="mean"
    )

    # Imputer les valeurs manquantes par la médiane de chaque colonne
    matrix = matrix.fillna(matrix.median())

    return matrix


# ---------------------------------------------------------------------------
# Sélection automatique du nombre optimal de clusters (méthode silhouette)
# ---------------------------------------------------------------------------

def choisir_nb_clusters(X_scaled: np.ndarray, k_min: int = 3, k_max: int = 5) -> int:
    """
    Teste k_min à k_max clusters et retourne le k avec le meilleur score silhouette.
    Garantit que tous les États reçoivent un cluster (KMeans sans valeurs manquantes).
    """
    meilleur_k = k_min
    meilleur_score = -1

    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        print(f"  k={k} → silhouette score = {score:.4f}")
        if score > meilleur_score:
            meilleur_score = score
            meilleur_k = k

    print(f"\n  → Nombre optimal de clusters retenu : {meilleur_k} (score={meilleur_score:.4f})")
    return meilleur_k


# ---------------------------------------------------------------------------
# Classification principale
# ---------------------------------------------------------------------------

def classifier_etats(engine, export_path: str) -> pd.DataFrame:
    """
    Pipeline complet :
    1. Charge la matrice de risque
    2. Normalise (StandardScaler)
    3. Sélectionne le meilleur k (silhouette)
    4. Applique K-Means
    5. Exporte en CSV
    Retourne le DataFrame avec la colonne 'cluster'.
    """
    print("\n[1/4] Chargement de la matrice de risque...")
    matrix = load_risk_matrix(engine)
    print(f"  {matrix.shape[0]} États × {matrix.shape[1]} maladies chargés")

    print("\n[2/4] Normalisation des données...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(matrix.values)

    print("\n[3/4] Sélection du nombre de clusters (3 à 5)...")
    k_optimal = choisir_nb_clusters(X_scaled, k_min=3, k_max=5)

    print(f"\n[4/4] Application de K-Means (k={k_optimal})...")
    km_final = KMeans(n_clusters=k_optimal, random_state=42, n_init=10)
    clusters = km_final.fit_predict(X_scaled)

    # Construction du DataFrame résultat
    result = matrix.reset_index()[["location_abbr", "location_desc"]].copy()
    result["cluster"] = clusters + 1  # clusters numérotés à partir de 1

    # Vérification : 100% des États ont un cluster
    assert result["cluster"].isna().sum() == 0, "ERREUR : certains États n'ont pas de cluster !"
    print(f"\n  ✓ 100% des États classifiés ({len(result)} / {len(result)})")

    # Résumé par cluster
    print("\n  Résumé par cluster :")
    print(result.groupby("cluster")["location_abbr"].count().to_string())

    # Export CSV
    export_results(result, export_path)

    return result


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv()

    DB_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/chronic_disease_dwh"
    )

    print("=" * 60)
    print("  Classification des États — K-Means épidémiologique")
    print("=" * 60)

    engine = create_engine(DB_URL)

    classifier_etats(
        engine=engine,
        export_path="data/exports/risk_classification/clusters_etats.csv"
    )

    print("\nClassification terminée.")