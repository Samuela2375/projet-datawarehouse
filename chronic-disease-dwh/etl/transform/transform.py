"""
etl/transform/transform.py

Service de transformation pour le projet d'entrepôt de données
"U.S. Chronic Disease Indicators" (CDC).

Couvre l'étape "Intégration / Transformation" de l'architecture ETL :
- Suppression des colonnes inutiles (footnotes, IDs redondants, etc.)
- Conversion de DataValue en numérique (avec repli sur DataValueAlt)
- Gestion des valeurs manquantes
- Séparation de GeoLocation en latitude / longitude
- Normalisation des noms d'États et des catégories de pathologies
- Export du CSV nettoyé dans data/cleaned/

Référence Issue #2 — Transformation et nettoyage.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# Colonnes jugées inutiles pour l'entrepôt de données : footnotes, IDs
# redondants déjà couverts par les colonnes "libellé", et stratifications
# secondaires/tertiaires presque entièrement vides (cf. dictionnaire_donnees.md).
UNUSED_COLUMNS: list[str] = [
    "Response",
    "DataValueFootnoteSymbol",
    "DatavalueFootnote",
    "ResponseID",
    "StratificationCategory2",
    "Stratification2",
    "StratificationCategoryID2",
    "StratificationID2",
    "StratificationCategory3",
    "Stratification3",
    "StratificationCategoryID3",
    "StratificationID3",
]

# Correction des variantes d'orthographe / libellés ambigus pour les États,
# afin qu'un même territoire ne soit jamais compté sous deux noms différents.
LOCATION_NAME_FIXES: dict[str, str] = {
    "United States": "United States",
    "U.S. Virgin Islands": "US Virgin Islands",
    "Virgin Islands": "US Virgin Islands",
    "DC": "District of Columbia",
}

# Format réel observé dans GeoLocation (cf. dictionnaire_donnees.md) :
# "(64.84507995700051, -147.72205903599973)" -> (latitude, longitude)
GEOLOCATION_PATTERN = re.compile(
    r"\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)"
)


class TransformationService:
    """
    Service de transformation du dataset CDC nettoyé à partir du CSV brut.

    Usage typique :
        service = TransformationService()
        df = service.drop_unused_columns(df)
        df = service.convert_data_value(df)
        df = service.handle_missing_values(df, strategy="drop")
        df = service.split_geolocation(df)
        df = service.normalize_location_names(df)
        df = service.normalize_topic_names(df)
        service.export_cleaned_csv(df, "data/cleaned/chronic_disease_cleaned.csv")
    """

    def __init__(self, unused_columns: list[str] | None = None):
        self.unused_columns = unused_columns or UNUSED_COLUMNS

    # ------------------------------------------------------------------ #
    # 1. Suppression des colonnes inutiles
    # ------------------------------------------------------------------ #
    def drop_unused_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Retire les colonnes non nécessaires à l'entrepôt de données
        (footnotes, IDs redondants, stratifications secondaires/tertiaires).

        Args:
            df: DataFrame source.

        Returns:
            pd.DataFrame: DataFrame sans les colonnes inutiles.
        """
        before = df.shape[1]
        cols_to_drop = [c for c in self.unused_columns if c in df.columns]
        df = df.drop(columns=cols_to_drop)

        logger.info(
            "[drop_unused_columns] %d colonnes retirées (%d -> %d colonnes) : %s",
            len(cols_to_drop), before, df.shape[1], cols_to_drop,
        )
        return df

    # ------------------------------------------------------------------ #
    # 2. Conversion de DataValue en numérique
    # ------------------------------------------------------------------ #
    def convert_data_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convertit DataValue en type numérique. Quand DataValue est manquant
        ou non numérique, se replie sur DataValueAlt (déjà numérique dans
        le dataset source).

        Args:
            df: DataFrame source.

        Returns:
            pd.DataFrame: DataFrame avec DataValue garanti numérique (float).
        """
        n_total = len(df)

        df["DataValue"] = pd.to_numeric(df["DataValue"], errors="coerce")

        if "DataValueAlt" in df.columns:
            df["DataValueAlt"] = pd.to_numeric(df["DataValueAlt"], errors="coerce")
            n_filled_from_alt = (df["DataValue"].isna() & df["DataValueAlt"].notna()).sum()
            df["DataValue"] = df["DataValue"].fillna(df["DataValueAlt"])
        else:
            n_filled_from_alt = 0

        n_still_missing = df["DataValue"].isna().sum()

        logger.info(
            "[convert_data_value] %d valeurs récupérées via DataValueAlt, "
            "%d/%d lignes encore sans valeur numérique après conversion.",
            n_filled_from_alt, n_still_missing, n_total,
        )
        return df

    # ------------------------------------------------------------------ #
    # 3. Gestion des valeurs manquantes
    # ------------------------------------------------------------------ #
    def handle_missing_values(
        self, df: pd.DataFrame, strategy: str = "drop"
    ) -> pd.DataFrame:
        """
        Gère les valeurs manquantes restantes dans DataValue.

        Args:
            df: DataFrame source.
            strategy: "drop" pour supprimer les lignes sans valeur,
                "fill_zero" pour les remplacer par 0.

        Returns:
            pd.DataFrame: DataFrame traité.

        Raises:
            ValueError: si la stratégie demandée n'est pas reconnue.
        """
        before = len(df)

        if strategy == "drop":
            df = df.dropna(subset=["DataValue"])
        elif strategy == "fill_zero":
            df["DataValue"] = df["DataValue"].fillna(0)
        else:
            raise ValueError(f"Stratégie inconnue : '{strategy}' (attendu : 'drop' ou 'fill_zero')")

        after = len(df)
        pct_treated = round((before - after) / before * 100, 2) if before else 0.0

        logger.info(
            "[handle_missing_values] stratégie='%s' : %d lignes traitées "
            "(%.2f%% du total) -> %d lignes restantes (%d -> %d).",
            strategy, before - after, pct_treated, after, before, after,
        )
        return df

    # ------------------------------------------------------------------ #
    # 4. Séparation de GeoLocation en latitude / longitude
    # ------------------------------------------------------------------ #
    def split_geolocation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extrait latitude et longitude depuis la colonne GeoLocation, au
        format réel "(latitude, longitude)" observé dans le dataset CDC,
        puis supprime la colonne d'origine.

        Args:
            df: DataFrame source contenant une colonne GeoLocation.

        Returns:
            pd.DataFrame: DataFrame avec colonnes latitude/longitude ajoutées.
        """
        before_valid = df["GeoLocation"].notna().sum() if "GeoLocation" in df.columns else 0

        def parse_point(value):
            if pd.isna(value):
                return (None, None)
            match = GEOLOCATION_PATTERN.match(str(value).strip())
            if not match:
                return (None, None)
            latitude, longitude = float(match.group(1)), float(match.group(2))
            return (latitude, longitude)

        coords = df["GeoLocation"].apply(parse_point)
        df["latitude"] = coords.apply(lambda c: c[0])
        df["longitude"] = coords.apply(lambda c: c[1])
        df = df.drop(columns=["GeoLocation"])

        after_valid = df["latitude"].notna().sum()
        logger.info(
            "[split_geolocation] %d/%d coordonnées extraites avec succès.",
            after_valid, before_valid,
        )
        return df

    # ------------------------------------------------------------------ #
    # 5. Normalisation des noms d'États
    # ------------------------------------------------------------------ #
    def normalize_location_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Uniformise les libellés d'États/territoires (LocationDesc) pour
        garantir qu'aucun territoire n'apparaît sous deux orthographes
        différentes.

        Args:
            df: DataFrame source.

        Returns:
            pd.DataFrame: DataFrame avec LocationDesc normalisé.
        """
        before_unique = df["LocationDesc"].nunique()

        df["LocationDesc"] = (
            df["LocationDesc"].astype(str).str.strip().replace(LOCATION_NAME_FIXES)
        )

        after_unique = df["LocationDesc"].nunique()
        logger.info(
            "[normalize_location_names] %d -> %d libellés uniques d'États.",
            before_unique, after_unique,
        )
        return df

    # ------------------------------------------------------------------ #
    # 6. Normalisation des catégories de pathologies
    # ------------------------------------------------------------------ #
    def normalize_topic_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Uniformise la casse et les espaces des libellés de Topic
        (catégorie de pathologie) pour éviter les doublons silencieux.

        Args:
            df: DataFrame source.

        Returns:
            pd.DataFrame: DataFrame avec Topic normalisé.
        """
        before_unique = df["Topic"].nunique()

        df["Topic"] = df["Topic"].astype(str).str.strip().str.title()

        after_unique = df["Topic"].nunique()
        logger.info(
            "[normalize_topic_names] %d -> %d catégories de pathologies uniques.",
            before_unique, after_unique,
        )
        return df

    # ------------------------------------------------------------------ #
    # 7. Export du CSV nettoyé
    # ------------------------------------------------------------------ #
    def export_cleaned_csv(self, df: pd.DataFrame, path: str | Path) -> Path:
        """
        Exporte le DataFrame nettoyé au format CSV.

        Args:
            df: DataFrame nettoyé à exporter.
            path: chemin de sortie (ex: data/cleaned/chronic_disease_cleaned.csv)

        Returns:
            Path: chemin du fichier généré.
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        logger.info(
            "[export_cleaned_csv] %d lignes, %d colonnes exportées vers %s",
            len(df), df.shape[1], output_path,
        )
        return output_path


# ---------------------------------------------------------------------- #
# Exécution directe en script (acceptance criteria : pipeline reproductible
# en une commande, sans erreur, avec traçabilité du nombre de lignes
# à chaque étape via les logs ci-dessus).
# ---------------------------------------------------------------------- #
def main():
    """Point d'entrée CLI : exécute le pipeline de transformation complet."""
    # Même logique de chemins que extract.py : le script se trouve dans
    # chronic-disease-dwh/etl/transform/transform.py, le CSV brut est suivi
    # par Git LFS à la racine du dépôt (repo_root/data/raw/...), et le CSV
    # nettoyé est écrit dans le sous-dossier applicatif (app_root/data/cleaned/).
    app_root = Path(__file__).resolve().parents[2]  # .../chronic-disease-dwh
    repo_root = app_root.parent                      # .../projet-datawarehouse
    raw_csv_path = repo_root / "data" / "raw" / "U.S._Chronic_Disease_Indicators.csv"
    cleaned_csv_path = app_root / "data" / "cleaned" / "chronic_disease_cleaned.csv"

    logger.info("Lecture du fichier brut : %s", raw_csv_path)
    df = pd.read_csv(raw_csv_path, low_memory=False)
    logger.info("-> %d lignes, %d colonnes au départ.", len(df), df.shape[1])

    service = TransformationService()

    df = service.drop_unused_columns(df)
    df = service.convert_data_value(df)
    df = service.handle_missing_values(df, strategy="drop")
    df = service.split_geolocation(df)
    df = service.normalize_location_names(df)
    df = service.normalize_topic_names(df)

    output_path = service.export_cleaned_csv(df, cleaned_csv_path)

    print("\nTransformation terminée avec succès :")
    print(f"  - Lignes finales   : {len(df):,}".replace(",", " "))
    print(f"  - Colonnes finales : {df.shape[1]}")
    print(f"  - Fichier exporté  : {output_path}\n")


if __name__ == "__main__":
    main()