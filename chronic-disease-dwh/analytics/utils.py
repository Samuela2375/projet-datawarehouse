# =============================================================================
# analytics/utils.py
# Fonctions utilitaires partagées par tous les scripts analytics
# =============================================================================

import os
import pandas as pd
from sqlalchemy import text


def run_query(query_path: str, conn) -> pd.DataFrame:
    """
    Lit un fichier .sql depuis query_path et exécute la requête
    via la connexion SQLAlchemy fournie.

    Paramètres
    ----------
    query_path : str
        Chemin vers le fichier .sql (ex: 'analytics/prevalence/top_diseases.sql')
    conn : sqlalchemy.engine.Connection
        Connexion active à la base PostgreSQL

    Retourne
    --------
    pd.DataFrame : résultat de la requête
    """
    with open(query_path, "r", encoding="utf-8") as f:
        sql = f.read()
    return pd.read_sql(text(sql), conn)


def export_results(df: pd.DataFrame, path: str) -> None:
    """
    Exporte un DataFrame pandas en fichier CSV.
    Crée automatiquement les dossiers parents si nécessaires.

    Paramètres
    ----------
    df : pd.DataFrame
        Résultat à exporter
    path : str
        Chemin complet du fichier CSV de sortie
        (ex: 'data/exports/prevalence/top_diseases.csv')
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  ✓ Exporté → {path}  ({len(df)} lignes)")