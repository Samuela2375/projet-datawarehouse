"""
verify_pipeline.py
===================
Vérification globale de la qualité et de la cohérence des données
après exécution du pipeline ETL — Chronic Disease Data Warehouse.

Contrôles effectués :
    1. Les 7 tables attendues (6 dimensions + fact_disease_indicator)
       contiennent des données.
    2. Aucune clé étrangère orpheline (dimensions <-> faits).
    3. Le volume de données est cohérent entre le CSV nettoyé et
       la table de faits chargée.

Usage :
    python verify_pipeline.py

Code de sortie : 0 si tous les contrôles passent, 1 sinon.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("verify_pipeline")

ROOT = Path(__file__).resolve().parent
PROJECT_DIR = ROOT / "chronic-disease-dwh"
CLEANED_CSV = PROJECT_DIR / "data" / "cleaned" / "chronic_disease_cleaned.csv"
VOLUME_TOLERANCE = 0.01  # 1 %, cohérent avec LoadService.verify_row_counts

load_dotenv(PROJECT_DIR / ".env")


def get_connection() -> psycopg2.extensions.connection:
    """Retourne une connexion PostgreSQL depuis les variables d'environnement."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "chronic_disease_dwh"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Résultat d'un contrôle
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# Contrôle 1 — Tables non vides
# ---------------------------------------------------------------------------

# Les 7 tables produites par LoadService.run() (6 dimensions + le fait principal).
CORE_TABLES = [
    "dim_time",
    "dim_location",
    "dim_topic",
    "dim_question",
    "dim_stratification",
    "dim_data_source",
    "fact_disease_indicator",
]

# fact_risk_factor est un fait dérivé (calculé après coup) : vérifié séparément,
# hors du compte des "7 tables attendues".
DERIVED_TABLES = ["fact_risk_factor"]


def check_table_not_empty(conn, table: str) -> CheckResult:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        count = row[0] if row else 0
    passed = count > 0
    detail = f"{count} ligne(s)" if passed else "table vide"
    log.info("  [%s] %s → %s", "OK" if passed else "ÉCHEC", table, detail)
    return CheckResult(f"table_non_vide::{table}", passed, detail)


# ---------------------------------------------------------------------------
# Contrôle 2 — Clés étrangères orphelines
# ---------------------------------------------------------------------------

# (table source, colonne FK, table cible, colonne PK, nullable)
FK_RELATIONS: list[tuple[str, str, str, str, bool]] = [
    ("fact_disease_indicator", "time_id",           "dim_time",           "time_id",           False),
    ("fact_disease_indicator", "location_id",        "dim_location",       "location_id",       False),
    ("fact_disease_indicator", "topic_id",           "dim_topic",          "topic_id",          False),
    ("fact_disease_indicator", "question_id",        "dim_question",       "question_id",       False),
    ("fact_disease_indicator", "stratification_id",  "dim_stratification", "stratification_id", False),
    ("fact_disease_indicator", "source_id",          "dim_data_source",    "source_id",         True),
    ("dim_question",           "topic_id",           "dim_topic",          "topic_id",          False),
    ("fact_risk_factor",       "location_id",        "dim_location",       "location_id",       False),
    ("fact_risk_factor",       "time_id",            "dim_time",           "time_id",           False),
    ("fact_risk_factor",       "topic_id",           "dim_topic",          "topic_id",          False),
]


def check_no_orphan_fk(
    conn, fact_table: str, fk_col: str, dim_table: str, pk_col: str, nullable: bool
) -> CheckResult:
    null_clause = f"AND f.{fk_col} IS NOT NULL" if nullable else ""
    sql = f"""
        SELECT COUNT(*)
        FROM {fact_table} f
        LEFT JOIN {dim_table} d ON f.{fk_col} = d.{pk_col}
        WHERE d.{pk_col} IS NULL {null_clause}
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        orphan_count = row[0] if row else 0
    passed = orphan_count == 0
    detail = "0 orpheline" if passed else f"{orphan_count} ligne(s) orpheline(s)"
    label = f"{fact_table}.{fk_col} → {dim_table}.{pk_col}"
    log.info("  [%s] %s → %s", "OK" if passed else "ÉCHEC", label, detail)
    return CheckResult(f"fk_orpheline::{label}", passed, detail)


# ---------------------------------------------------------------------------
# Contrôle 3 — Cohérence des volumes (CSV nettoyé vs table de faits)
# ---------------------------------------------------------------------------

def check_volume_consistency(conn) -> CheckResult:
    if not CLEANED_CSV.exists():
        detail = f"fichier introuvable : {CLEANED_CSV}"
        log.warning("  [IGNORÉ] cohérence des volumes → %s", detail)
        return CheckResult("coherence_volumes", False, detail)

    with CLEANED_CSV.open("r", encoding="utf-8") as fh:
        csv_row_count = sum(1 for _ in fh) - 1  # moins l'en-tête

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fact_disease_indicator")
        row = cur.fetchone()
        db_count = row[0] if row else 0

    ecart = abs(db_count - csv_row_count) / max(csv_row_count, 1)
    passed = ecart <= VOLUME_TOLERANCE
    detail = (
        f"CSV={csv_row_count} lignes, BDD={db_count} lignes, "
        f"écart={ecart * 100:.2f}% (tolérance {VOLUME_TOLERANCE * 100:.0f}%)"
    )
    log.info("  [%s] cohérence des volumes → %s", "OK" if passed else "ÉCHEC", detail)
    return CheckResult("coherence_volumes", passed, detail)


# ---------------------------------------------------------------------------
# Orchestration des contrôles
# ---------------------------------------------------------------------------

def run_all_checks(conn) -> list[CheckResult]:
    results: list[CheckResult] = []

    log.info("=" * 64)
    log.info("Contrôle 1/3 — Présence de données dans les 7 tables attendues")
    log.info("=" * 64)
    for table in CORE_TABLES:
        results.append(check_table_not_empty(conn, table))
    for table in DERIVED_TABLES:
        log.info("  (table dérivée, vérifiée séparément)")
        results.append(check_table_not_empty(conn, table))

    log.info("=" * 64)
    log.info("Contrôle 2/3 — Absence de clés étrangères orphelines")
    log.info("=" * 64)
    for fact_table, fk_col, dim_table, pk_col, nullable in FK_RELATIONS:
        results.append(check_no_orphan_fk(conn, fact_table, fk_col, dim_table, pk_col, nullable))

    log.info("=" * 64)
    log.info("Contrôle 3/3 — Cohérence des volumes entre les étapes")
    log.info("=" * 64)
    results.append(check_volume_consistency(conn))

    return results


def main() -> int:
    log.info("Démarrage de la vérification globale du pipeline")

    try:
        conn = get_connection()
    except Exception as exc:
        log.error("Impossible de se connecter à la base de données : %s", exc)
        return 1

    try:
        results = run_all_checks(conn)
    finally:
        conn.close()

    failures = [r for r in results if not r.passed]

    log.info("=" * 64)
    log.info("RÉSUMÉ : %d contrôle(s) exécuté(s), %d échec(s)", len(results), len(failures))
    log.info("=" * 64)

    if failures:
        log.error("Vérification ÉCHOUÉE. Détail des contrôles en échec :")
        for f in failures:
            log.error("  - %s : %s", f.name, f.detail)
        return 1

    log.info("Vérification RÉUSSIE — toutes les données sont cohérentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())