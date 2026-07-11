"""
run_pipeline.py
================
Point d'entrée unique du pipeline ETL — Chronic Disease Data Warehouse.

Enchaîne automatiquement, sans intervention manuelle :
    1. Extraction    (etl/extract/extract.py)
    2. Transformation (etl/transform/transform.py)
    3. Chargement     (etl/load/load.py)

Usage :
    python run_pipeline.py

Le script s'arrête dès qu'une étape échoue (fail-fast) et retourne
un code de sortie non nul, pour rester facilement intégrable dans un
cron, une CI, ou tout autre orchestrateur.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run_pipeline")

# ---------------------------------------------------------------------------
# Définition des étapes du pipeline
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent

# Le code ETL vit dans le sous-dossier du projet ; les scripts internes
# (extract.py, transform.py, load.py) utilisent des chemins relatifs
# (ex: "data/cleaned/...") qui supposent d'être exécutés depuis ce dossier.
PROJECT_DIR = ROOT / "chronic-disease-dwh"

# Adapter ces chemins si l'organisation du dépôt diffère.
STEPS: list[tuple[str, Path]] = [
    ("EXTRACTION",     PROJECT_DIR / "etl" / "extract"   / "extract.py"),
    ("TRANSFORMATION", PROJECT_DIR / "etl" / "transform"  / "transform.py"),
    ("CHARGEMENT",      PROJECT_DIR / "etl" / "load"       / "load.py"),
]


class PipelineStepError(RuntimeError):
    """Levée quand une étape du pipeline échoue, pour interrompre proprement."""

    def __init__(self, step_name: str, returncode: int) -> None:
        super().__init__(f"Étape « {step_name} » terminée avec le code {returncode}")
        self.step_name = step_name
        self.returncode = returncode


# ---------------------------------------------------------------------------
# Exécution d'une étape
# ---------------------------------------------------------------------------

def run_step(step_name: str, script_path: Path) -> None:
    """Exécute un script d'étape dans un sous-processus et lève en cas d'échec."""
    if not script_path.exists():
        raise FileNotFoundError(f"Script introuvable pour l'étape « {step_name} » : {script_path}")

    log.info("=" * 64)
    log.info("Étape : %s  (%s)", step_name, script_path.relative_to(ROOT))
    log.info("=" * 64)

    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_DIR,
    )
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        log.error("Étape « %s » ÉCHOUÉE après %.2fs (code %d)", step_name, elapsed, result.returncode)
        raise PipelineStepError(step_name, result.returncode)

    log.info("Étape « %s » terminée avec succès (%.2fs)", step_name, elapsed)


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Démarrage du pipeline ETL complet (%d étapes)", len(STEPS))
    pipeline_start = time.perf_counter()

    for step_name, script_path in STEPS:
        run_step(step_name, script_path)

    total = time.perf_counter() - pipeline_start
    log.info("=" * 64)
    log.info("Pipeline terminé avec succès en %.2fs", total)
    log.info("=" * 64)


if __name__ == "__main__":
    try:
        main()
    except PipelineStepError as exc:
        log.error("Arrêt du pipeline : %s", exc)
        sys.exit(1)
    except FileNotFoundError as exc:
        log.error("Arrêt du pipeline : %s", exc)
        sys.exit(1)
    except Exception:
        log.exception("Erreur inattendue — arrêt du pipeline")
        sys.exit(1)