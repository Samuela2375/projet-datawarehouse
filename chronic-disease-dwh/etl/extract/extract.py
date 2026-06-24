"""
etl/extract/extract.py

Service d'extraction pour le projet d'entrepôt de données
"U.S. Chronic Disease Indicators" (CDC).

Couvre l'étape "Acquisition" de l'architecture ETL :
- Lecture robuste du CSV brut déposé dans data/raw/
- Validation des colonnes attendues avant transformation
- Génération d'un résumé statistique du dataset
- Export automatique du dictionnaire de données (docs/dictionnaire_donnees.md)

Référence Issue #1 — Extraction des données.
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# Colonnes attendues dans le dataset officiel CDC "U.S. Chronic Disease
# Indicators" (34 colonnes au total, ordre tel que publié par le CDC).
EXPECTED_COLUMNS: list[str] = [
    "YearStart",
    "YearEnd",
    "LocationAbbr",
    "LocationDesc",
    "DataSource",
    "Topic",
    "Question",
    "Response",
    "DataValueUnit",
    "DataValueType",
    "DataValue",
    "DataValueAlt",
    "DataValueFootnoteSymbol",
    "DatavalueFootnote",
    "LowConfidenceLimit",
    "HighConfidenceLimit",
    "StratificationCategory1",
    "Stratification1",
    "StratificationCategory2",
    "Stratification2",
    "StratificationCategory3",
    "Stratification3",
    "GeoLocation",
    "ResponseID",
    "LocationID",
    "TopicID",
    "QuestionID",
    "DataValueTypeID",
    "StratificationCategoryID1",
    "StratificationID1",
    "StratificationCategoryID2",
    "StratificationID2",
    "StratificationCategoryID3",
    "StratificationID3",
]

MIN_EXPECTED_COLUMNS = 34


class ColumnValidationError(Exception):
    """Levée quand une ou plusieurs colonnes attendues sont absentes du CSV."""


class ExtractionService:
    """
    Service d'extraction du dataset brut CDC.

    Usage typique :
        service = ExtractionService()
        df = service.load_raw_csv("data/raw/U.S._Chronic_Disease_Indicators.csv")
        service.validate_columns(df)
        summary = service.get_dataset_summary(df)
        service.export_summary_report(df, "docs/dictionnaire_donnees.md")
    """

    def __init__(self, expected_columns: list[str] | None = None):
        self.expected_columns = expected_columns or EXPECTED_COLUMNS

    # ------------------------------------------------------------------ #
    # 1. Lecture robuste du CSV
    # ------------------------------------------------------------------ #
    def load_raw_csv(self, filepath: str | Path) -> pd.DataFrame:
        """
        Charge le CSV brut en DataFrame pandas.

        - Vérifie que le fichier existe.
        - Lit le fichier avec un encodage tolérant (utf-8, fallback latin-1).
        - Vérifie que le DataFrame n'est pas vide.

        Args:
            filepath: chemin vers le fichier CSV (ex: data/raw/...csv)

        Returns:
            pd.DataFrame: les données brutes chargées.

        Raises:
            FileNotFoundError: si le fichier n'existe pas.
            ValueError: si le fichier est vide ou illisible.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(
                f"Fichier introuvable : {path}. "
                "Vérifiez qu'il est bien présent dans data/raw/ "
                "(et que Git LFS a bien été utilisé si le fichier provient du dépôt Git)."
            )

        logger.info("Lecture du fichier CSV : %s", path)

        try:
            df = pd.read_csv(path, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            logger.warning(
                "Échec de lecture en UTF-8, nouvelle tentative en latin-1."
            )
            df = pd.read_csv(path, encoding="latin-1", low_memory=False)
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"Le fichier {path} est vide.") from exc

        if df.empty:
            raise ValueError(f"Le fichier {path} a été lu mais ne contient aucune ligne.")

        logger.info(
            "CSV chargé avec succès : %d lignes, %d colonnes.",
            len(df),
            len(df.columns),
        )
        return df

    # ------------------------------------------------------------------ #
    # 2. Validation des colonnes
    # ------------------------------------------------------------------ #
    def validate_columns(self, df: pd.DataFrame) -> bool:
        """
        Valide que toutes les colonnes attendues sont présentes dans le DataFrame,
        et que le nombre total de colonnes respecte le minimum requis (34).

        Args:
            df: DataFrame à valider.

        Returns:
            bool: True si la validation réussit.

        Raises:
            ColumnValidationError: si une colonne attendue est absente,
                ou si le nombre de colonnes est inférieur au minimum requis.
        """
        missing_columns = [col for col in self.expected_columns if col not in df.columns]

        if missing_columns:
            raise ColumnValidationError(
                f"Colonnes manquantes dans le dataset : {missing_columns}. "
                f"Colonnes attendues ({len(self.expected_columns)}) : {self.expected_columns}"
            )

        if len(df.columns) < MIN_EXPECTED_COLUMNS:
            raise ColumnValidationError(
                f"Le dataset contient seulement {len(df.columns)} colonnes, "
                f"alors que {MIN_EXPECTED_COLUMNS} sont attendues au minimum."
            )

        logger.info(
            "Validation des colonnes réussie : %d colonnes présentes (>= %d attendues).",
            len(df.columns),
            MIN_EXPECTED_COLUMNS,
        )
        return True

    # ------------------------------------------------------------------ #
    # 3. Résumé statistique du dataset
    # ------------------------------------------------------------------ #
    def get_dataset_summary(self, df: pd.DataFrame) -> dict:
        """
        Calcule un résumé statistique du dataset : nombre de lignes, de colonnes,
        et pourcentage de valeurs manquantes par colonne.

        Args:
            df: DataFrame à résumer.

        Returns:
            dict avec les clés :
                - n_rows (int)
                - n_cols (int)
                - missing_pct (dict[str, float]) : % de valeurs manquantes par colonne
                - dtypes (dict[str, str]) : type de données par colonne
        """
        n_rows = len(df)
        n_cols = len(df.columns)

        missing_pct = (df.isna().sum() / n_rows * 100).round(2).to_dict() if n_rows else {}
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

        summary = {
            "n_rows": n_rows,
            "n_cols": n_cols,
            "missing_pct": missing_pct,
            "dtypes": dtypes,
        }

        logger.info(
            "Résumé du dataset : %d lignes, %d colonnes.", n_rows, n_cols
        )
        return summary

    # ------------------------------------------------------------------ #
    # 4. Export du dictionnaire de données
    # ------------------------------------------------------------------ #
    def export_summary_report(self, df: pd.DataFrame, path: str | Path) -> Path:
        """
        Génère automatiquement le dictionnaire de données du dataset au format
        Markdown, incluant pour chaque colonne : son type, son pourcentage de
        valeurs manquantes, et un exemple de valeur.

        Args:
            df: DataFrame source.
            path: chemin de sortie du fichier Markdown (ex: docs/dictionnaire_donnees.md)

        Returns:
            Path: chemin du fichier généré.
        """
        summary = self.get_dataset_summary(df)
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Dictionnaire de données",
            "",
            f"_Généré automatiquement le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            "",
            "## Résumé général",
            "",
            f"- **Nombre de lignes** : {summary['n_rows']:,}".replace(",", " "),
            f"- **Nombre de colonnes** : {summary['n_cols']}",
            "",
            "## Détail des colonnes",
            "",
            "| Colonne | Type | % valeurs manquantes | Exemple de valeur |",
            "|---|---|---|---|",
        ]

        for col in df.columns:
            dtype = summary["dtypes"].get(col, "object")
            missing = summary["missing_pct"].get(col, 0.0)
            non_null_series = df[col].dropna()
            example = non_null_series.iloc[0] if not non_null_series.empty else ""
            example_str = str(example).replace("|", "\\|")
            if len(example_str) > 50:
                example_str = example_str[:47] + "..."
            lines.append(f"| `{col}` | {dtype} | {missing}% | {example_str} |")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Dictionnaire de données généré : %s", output_path)
        return output_path


# ---------------------------------------------------------------------- #
# Exécution directe en script (acceptance criteria : exécutable en une
# commande, sans erreur).
# ---------------------------------------------------------------------- #
def main():
    """Point d'entrée CLI : exécute le pipeline d'extraction complet."""
    # Le script se trouve dans chronic-disease-dwh/etl/extract/extract.py
    # mais le CSV brut est suivi par Git/LFS à la racine du dépôt
    # (repo_root/data/raw/...), tandis que le dictionnaire de données
    # reste dans chronic-disease-dwh/docs/ (sous-dossier applicatif suivi par Git).
    app_root = Path(__file__).resolve().parents[2]  # .../chronic-disease-dwh
    repo_root = app_root.parent                      # .../projet-datawarehouse
    csv_path = repo_root / "data" / "raw" / "U.S._Chronic_Disease_Indicators.csv"
    report_path = app_root / "docs" / "dictionnaire_donnees.md"

    service = ExtractionService()

    df = service.load_raw_csv(csv_path)
    service.validate_columns(df)
    summary = service.get_dataset_summary(df)

    print(f"\nDataset chargé avec succès :")
    print(f"  - Lignes  : {summary['n_rows']:,}".replace(",", " "))
    print(f"  - Colonnes: {summary['n_cols']}")

    report_path_out = service.export_summary_report(df, report_path)
    print(f"  - Dictionnaire de données exporté vers : {report_path_out}\n")


if __name__ == "__main__":
    main()