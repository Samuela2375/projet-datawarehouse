"""
etl/load/load.py
================
LoadService — chargement idempotent du Data Warehouse (Star Schema PostgreSQL).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, cast  # Ajout de cast pour les types

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connexion PostgreSQL
# ---------------------------------------------------------------------------

load_dotenv()


def get_connection() -> psycopg2.extensions.connection:
    """Retourne une connexion PostgreSQL depuis les variables d'environnement."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "chronic_disease_dwh"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# ===========================================================================
# LoadService
# ===========================================================================

class LoadService:
    """
    Chargement idempotent du Data Warehouse.
    """

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn
        # Dicts de lookup {clé_naturelle → id} remplis par les méthodes load_dim_*
        self._time_map:   dict[tuple[int, int], int] = {}
        self._loc_map:    dict[str, int]   = {}
        self._topic_map:  dict[str, int]   = {}
        self._quest_map:  dict[str, int]   = {}
        self._strat_map:  dict[tuple[str, str], int] = {}
        self._source_map: dict[str, int]   = {}

    # -----------------------------------------------------------------------
    # Helpers internes
    # -----------------------------------------------------------------------

    def _execute_many(self, sql: str, records: list[tuple[Any, ...]]) -> None:
        """Exécute un INSERT en lot, en ignorant les conflits."""
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=1000)
        self.conn.commit()

    def _fetch_lookup(self, sql: str) -> list[tuple[Any, ...]]:
        """Retourne toutes les lignes d'une requête SELECT."""
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    # -----------------------------------------------------------------------
    # Dimensions
    # -----------------------------------------------------------------------

    def load_dim_time(self, df: pd.DataFrame) -> None:
        """
        Insère les couples (year_start, year_end) uniques.
        """
        log.info("Chargement DIM_TIME…")
        pairs = df[["YearStart", "YearEnd"]].drop_duplicates().dropna()
        
        # Correction Pylance : cast en float avant le int pour garantir la compatibilité
        records = [
            (int(cast(float, r.YearStart)), int(cast(float, r.YearEnd))) 
            for r in pairs.itertuples()
        ]

        self._execute_many(
            """
            INSERT INTO dim_time (year_start, year_end)
            VALUES (%s, %s)
            ON CONFLICT (year_start, year_end) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup("SELECT time_id, year_start, year_end FROM dim_time")
        self._time_map = {(int(r[1]), int(r[2])): int(r[0]) for r in rows}
        log.info("  → %d entrées dans DIM_TIME", len(self._time_map))

    def load_dim_location(self, df: pd.DataFrame) -> None:
        """
        Insère les États/territoires uniques avec leur géolocalisation.
        Remplit self._loc_map : {location_abbr → location_id}.
        """
        log.info("Chargement DIM_LOCATION…")
        
        # Correction des noms de colonnes : latitude et longitude en minuscules
        cols = ["LocationAbbr", "LocationDesc", "latitude", "longitude"]
        
        # Extraction en utilisant les colonnes existantes
        locs = df[cols].drop_duplicates(subset=["LocationAbbr"]).dropna(subset=["LocationAbbr"])
        
        records = [
            (
                str(r.LocationAbbr).strip().upper(),
                str(r.LocationDesc).strip(),
                _to_float(r.latitude),  # Minuscule ici aussi
                _to_float(r.longitude), # Minuscule ici aussi
            )
            for r in locs.itertuples()
        ]

        self._execute_many(
            """
            INSERT INTO dim_location (location_abbr, location_desc, latitude, longitude)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (location_abbr) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup("SELECT location_id, location_abbr FROM dim_location")
        self._loc_map = {r[1].strip(): r[0] for r in rows}
        log.info("  → %d entrées dans DIM_LOCATION", len(self._loc_map))

    def load_dim_topic(self, df: pd.DataFrame) -> None:
        """
        Insère les catégories de pathologies uniques.
        """
        log.info("Chargement DIM_TOPIC…")
        topics = df["Topic"].drop_duplicates().dropna()
        records = [
            (str(t).strip(), True, "Medium")
            for t in topics
        ]

        self._execute_many(
            """
            INSERT INTO dim_topic (topic_name, is_chronic, risk_level)
            VALUES (%s, %s, %s)
            ON CONFLICT (topic_name) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup("SELECT topic_id, topic_name FROM dim_topic")
        self._topic_map = {r[1].strip(): r[0] for r in rows}
        log.info("  → %d entrées dans DIM_TOPIC", len(self._topic_map))

    def load_dim_question(self, df: pd.DataFrame) -> None:
        """
        Insère les questions/indicateurs uniques liés à leur topic.
        """
        log.info("Chargement DIM_QUESTION…")
        questions = df[["Question", "Topic"]].drop_duplicates(subset=["Question"]).dropna(subset=["Question"])
        records = [
            (str(r.Question).strip(), self._topic_map[str(r.Topic).strip()])
            for r in questions.itertuples()
            if str(r.Topic).strip() in self._topic_map
        ]

        self._execute_many(
            """
            INSERT INTO dim_question (question_text, topic_id)
            VALUES (%s, %s)
            ON CONFLICT (question_text) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup("SELECT question_id, question_text FROM dim_question")
        self._quest_map = {r[1].strip(): r[0] for r in rows}
        log.info("  → %d entrées dans DIM_QUESTION", len(self._quest_map))

    def load_dim_stratification(self, df: pd.DataFrame) -> None:
        """
        Insère les couples (catégorie, valeur) démographiques uniques.
        """
        log.info("Chargement DIM_STRATIFICATION…")
        strats = (
            df[["StratificationCategory1", "Stratification1"]]
            .drop_duplicates()
            .dropna()
        )
        records = [
            (str(r.StratificationCategory1).strip(), str(r.Stratification1).strip())
            for r in strats.itertuples()
        ]

        self._execute_many(
            """
            INSERT INTO dim_stratification (stratification_category, stratification_value)
            VALUES (%s, %s)
            ON CONFLICT (stratification_category, stratification_value) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup(
            "SELECT stratification_id, stratification_category, stratification_value FROM dim_stratification"
        )
        self._strat_map = {(r[1].strip(), r[2].strip()): r[0] for r in rows}
        log.info("  → %d entrées dans DIM_STRATIFICATION", len(self._strat_map))

    def load_dim_data_source(self, df: pd.DataFrame) -> None:
        """
        Insère les sources de données uniques.
        """
        log.info("Chargement DIM_DATA_SOURCE…")
        col = "DataSource" if "DataSource" in df.columns else None
        if col is None:
            log.warning("  Colonne DataSource absente — DIM_DATA_SOURCE non alimentée.")
            return

        sources = df[col].drop_duplicates().dropna()
        records = [(str(s).strip(),) for s in sources]

        self._execute_many(
            """
            INSERT INTO dim_data_source (source_name)
            VALUES (%s)
            ON CONFLICT (source_name) DO NOTHING
            """,
            records,
        )

        rows = self._fetch_lookup("SELECT source_id, source_name FROM dim_data_source")
        self._source_map = {r[1].strip(): r[0] for r in rows}
        log.info("  → %d entrées dans DIM_DATA_SOURCE", len(self._source_map))

    # -----------------------------------------------------------------------
    # Table de faits principale
    # -----------------------------------------------------------------------

    def load_fact_disease_indicator(self, df: pd.DataFrame) -> None:
        """
        Insère les lignes de FACT_DISEASE_INDICATOR.
        """
        log.info("Chargement FACT_DISEASE_INDICATOR…")

        records: list[tuple[Any, ...]] = []
        skipped = 0

        for row in df.itertuples(index=False):
            # --- Résolution des FK ---
            # Correction Pylance : cast en float pour permettre la conversion int
            time_key  = (int(cast(float, row.YearStart)), int(cast(float, row.YearEnd)))
            loc_key   = str(row.LocationAbbr).strip().upper()
            topic_key = str(row.Topic).strip()
            quest_key = str(row.Question).strip()
            strat_key = (
                str(row.StratificationCategory1).strip(),
                str(row.Stratification1).strip(),
            )
            source_key = str(getattr(row, "DataSource", "")).strip() or None

            time_id   = self._time_map.get(time_key)
            loc_id    = self._loc_map.get(loc_key)
            topic_id  = self._topic_map.get(topic_key)
            quest_id  = self._quest_map.get(quest_key)
            strat_id  = self._strat_map.get(strat_key)
            source_id = self._source_map.get(source_key) if source_key else None

            # Ignorer la ligne si une FK obligatoire est absente
            if None in (time_id, loc_id, topic_id, quest_id, strat_id):
                skipped += 1
                continue

            # --- Valeurs de mesure ---
            dv = _to_float(row.DataValue)
            ll = _to_float(row.LowConfidenceLimit)
            hl = _to_float(row.HighConfidenceLimit)
            dvt = str(getattr(row, "DataValueType", "")).strip() or None

            records.append((
                time_id, loc_id, topic_id, quest_id, strat_id, source_id,
                dv, dvt, ll, hl,
            ))

        if skipped:
            log.warning("  %d ligne(s) ignorée(s) (FK non résolues)", skipped)

        self._execute_many(
            """
            INSERT INTO fact_disease_indicator
                (time_id, location_id, topic_id, question_id, stratification_id, source_id,
                data_value, data_value_type, low_confidence_limit, high_confidence_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (time_id, location_id, topic_id, question_id, stratification_id, data_value_type)
            DO NOTHING
            """,
            records,
        )
        log.info("  → %d lignes insérées dans FACT_DISEASE_INDICATOR", len(records))

    # -----------------------------------------------------------------------
    # Table de faits complémentaire — risk_score
    # -----------------------------------------------------------------------

    def compute_and_load_risk_factor(self, _df: pd.DataFrame | None = None) -> None:
        """
        Calcule et charge FACT_RISK_FACTOR entièrement en SQL.
        """
        log.info("Calcul et chargement FACT_RISK_FACTOR…")

        sql = """
        WITH recent_years AS (
            SELECT
                f.location_id,
                f.topic_id,
                f.time_id,
                AVG(f.data_value) AS avg_recent
            FROM fact_disease_indicator f
            JOIN dim_time t ON f.time_id = t.time_id
            WHERE t.year_start >= (
                SELECT MAX(t2.year_start) - 4
                FROM dim_time t2
            )
            AND f.data_value IS NOT NULL
            GROUP BY f.location_id, f.topic_id, f.time_id
        ),
        normalized AS (
            SELECT
                location_id,
                topic_id,
                time_id,
                ROUND(
                    100.0 * avg_recent
                    / NULLIF(MAX(avg_recent) OVER (PARTITION BY topic_id), 0),
                2) AS risk_score
            FROM recent_years
        )
        INSERT INTO fact_risk_factor (location_id, time_id, topic_id, risk_score)
        SELECT location_id, time_id, topic_id, risk_score
        FROM normalized
        ON CONFLICT (location_id, time_id, topic_id) DO NOTHING
        """

        with self.conn.cursor() as cur:
            cur.execute(sql)
            inserted = cur.rowcount
        self.conn.commit()
        log.info("  → %d lignes insérées dans FACT_RISK_FACTOR", inserted)

    # -----------------------------------------------------------------------
    # Vérification des volumes
    # -----------------------------------------------------------------------

    def verify_row_counts(self, conn: psycopg2.extensions.connection, csv_row_count: int) -> None:
        """
        Compare le nombre de lignes du CSV source avec celui de FACT_DISEASE_INDICATOR.
        """
        log.info("Vérification des volumes…")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fact_disease_indicator")
            result = cur.fetchone()
            db_count = result[0] if result else 0

        ecart = abs(db_count - csv_row_count) / max(csv_row_count, 1) * 100

        log.info(
            "  CSV : %d lignes | BDD : %d lignes | Écart : %.2f %%",
            csv_row_count, db_count, ecart,
        )

        if ecart > 1.0:
            raise AssertionError(
                f"Écart entre le CSV ({csv_row_count} lignes) et "
                f"FACT_DISEASE_INDICATOR ({db_count} lignes) = {ecart:.2f} % > 1 %"
            )

        log.info("  ✔ Volumes OK (écart < 1 %%)")

    # -----------------------------------------------------------------------
    # Méthode principale
    # -----------------------------------------------------------------------

    def run(self, df: pd.DataFrame) -> None:
        """
        Exécute le pipeline complet.
        """
        csv_row_count = len(df)

        self.load_dim_time(df)
        self.load_dim_location(df)
        self.load_dim_topic(df)
        self.load_dim_question(df)
        self.load_dim_stratification(df)
        self.load_dim_data_source(df)

        self.load_fact_disease_indicator(df)
        self.compute_and_load_risk_factor()
        self.verify_row_counts(self.conn, csv_row_count)

        log.info("Pipeline de chargement terminé avec succès.")


# ===========================================================================
# Utilitaires
# ===========================================================================

def _to_float(value: Any) -> float | None:
    """Convertit une valeur en float, retourne None si impossible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ===========================================================================
# Point d'entrée
# ===========================================================================

def main() -> None:
    cleaned_path = Path("data/cleaned/chronic_disease_cleaned.csv")
    if not cleaned_path.exists():
        raise FileNotFoundError(
            f"Fichier nettoyé introuvable : {cleaned_path}\n"
            "Lancez d'abord : python etl/transform/transform.py"
        )

    log.info("Lecture du fichier nettoyé : %s", cleaned_path)
    df = pd.read_csv(cleaned_path, low_memory=False)
    log.info("  → %d lignes chargées", len(df))

    conn = get_connection()
    try:
        service = LoadService(conn)
        service.run(df)
    finally:
        conn.close()


if __name__ == "__main__":
    main()