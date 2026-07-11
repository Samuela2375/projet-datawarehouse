# Validation de bout en bout du pipeline ETL

## Contexte

Cette note documente la validation finale du pipeline ETL du projet `chronic-disease-dwh`, réalisée conformément à la sous-tâche D (« Validation de bout en bout »). L'objectif était de confirmer que le pipeline s'exécute intégralement, sans intervention manuelle, et que les données chargées respectent les contraintes de qualité définies pour l'entrepôt.

## Procédure suivie

1. Exécution de l'orchestrateur complet :
   ```
   python run_pipeline.py
   ```
   Enchaînement automatique des trois étapes — extraction, transformation, chargement — sans action manuelle entre chacune.

2. Exécution du script de vérification globale :
   ```
   python verify_pipeline.py
   ```

3. Analyse des logs produits par les deux scripts.

## Résultats

### `run_pipeline.py`

Les trois étapes du pipeline (EXTRACTION → TRANSFORMATION → CHARGEMENT) se sont exécutées dans l'ordre attendu, sans arrêt inattendu ni erreur. Le script s'est terminé avec un code de sortie `0`, en **178,32 secondes** au total.

| Étape | Durée | Résultat |
|---|---|---|
| EXTRACTION | 51,24 s | 403 984 lignes / 34 colonnes lues depuis `U.S._Chronic_Disease_Indicators.csv` ; dictionnaire de données généré dans `docs/dictionnaire_donnees.md` |
| TRANSFORMATION | 36,13 s | 12 colonnes retirées (34 → 22), 130 318 lignes sans valeur numérique supprimées (stratégie `drop`), géolocalisation éclatée (271 142 coordonnées extraites) → **273 666 lignes / 23 colonnes** exportées vers `data/cleaned/chronic_disease_cleaned.csv` |
| CHARGEMENT | 90,88 s | 6 dimensions + `fact_disease_indicator` chargées ; écart CSV/BDD de **0,20 %** (sous la tolérance de 1 %) |

Détail du chargement par table :

| Table | Lignes chargées |
|---|---|
| `dim_time` | 12 |
| `dim_location` | 55 |
| `dim_topic` | 17 |
| `dim_question` | 192 |
| `dim_stratification` | 10 |
| `dim_data_source` | 30 |
| `fact_disease_indicator` | 273 132 (sur 273 666 lignes source, écart 0,20 %) |
| `fact_risk_factor` (dérivée, calculée en SQL) | 3 340 |

> Note : l'écart de 534 lignes (0,20 %) entre le CSV nettoyé et `fact_disease_indicator` correspond aux lignes ignorées par `LoadService` faute de clé étrangère résolue (dimension manquante) — ce comportement est attendu et documenté dans `load_fact_disease_indicator()`, et reste très en dessous du seuil de tolérance de 1 %.

### `verify_pipeline.py`

Les trois contrôles de qualité ont tous été validés, pour un total de **19 contrôles exécutés, 0 échec** :

| Contrôle | Résultat |
|---|---|
| Présence de données dans les 7 tables attendues (`dim_time`, `dim_location`, `dim_topic`, `dim_question`, `dim_stratification`, `dim_data_source`, `fact_disease_indicator`) | ✅ OK — 12 / 55 / 17 / 192 / 10 / 30 / 273 132 lignes respectivement (aucune table vide). `fact_risk_factor` (table dérivée) contient 3 340 lignes. |
| Absence de clés étrangères orphelines (10 relations vérifiées) | ✅ OK — 0 orpheline sur les 6 FK de `fact_disease_indicator`, la FK de `dim_question` vers `dim_topic`, et les 3 FK de `fact_risk_factor` |
| Cohérence des volumes entre le CSV nettoyé et `fact_disease_indicator` | ✅ OK — CSV = 273 666 lignes, BDD = 273 132 lignes, écart = 0,20 % (tolérance 1 %) |

Le script s'est terminé avec le message `Vérification RÉUSSIE — toutes les données sont cohérentes.` et un code de sortie `0`.

## Conclusion

Le pipeline ETL est validé de bout en bout :

- Aucune intervention manuelle n'est nécessaire entre les étapes.
- Le résultat est reproductible : une nouvelle exécution complète (`run_pipeline.py` puis `verify_pipeline.py`) redonne un état cohérent, grâce à l'idempotence des insertions (`ON CONFLICT DO NOTHING`). Cette exécution en apporte d'ailleurs une preuve concrète : le log de chargement indique **0 nouvelle ligne insérée** dans `fact_risk_factor` (déjà peuplée par une exécution antérieure), alors que la table contient bien **3 340 lignes** au total selon `verify_pipeline.py` — confirmant qu'aucune donnée n'a été dupliquée lors de ce nouveau passage.
- Les contrôles de qualité automatisés couvrent les trois dimensions attendues : complétude, intégrité référentielle, cohérence volumétrique.

Cette validation clôture la sous-tâche D et confirme que le pipeline est prêt pour un usage répété (nouvelles données, ré-exécutions périodiques) sans risque de duplication ni d'incohérence.

---
*Date de validation : 11 juillet 2026*
*Environnement : exécution locale Windows (PowerShell, environnement virtuel `venv`), pipeline complet sur le jeu de données réel `U.S._Chronic_Disease_Indicators.csv` (403 984 lignes source)*