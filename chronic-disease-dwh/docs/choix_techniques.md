# Choix techniques du projet — Entrepôt de données Maladies Chroniques (CDC)

Ce document regroupe et justifie les principaux choix techniques réalisés dans le cadre du projet `chronic-disease-dwh`, un entrepôt de données destiné à l'analyse des maladies chroniques fréquentes aux États-Unis.

## 1. Choix du jeu de données : U.S. Chronic Disease Indicators (CDC)

Le projet s'appuie sur le jeu de données public **U.S. Chronic Disease Indicators**, publié par les *Centers for Disease Control and Prevention* (CDC).

**Justification :**
- **Fiabilité et légitimité de la source** : les données proviennent d'une agence sanitaire fédérale reconnue, ce qui garantit une méthodologie de collecte rigoureuse et une actualisation régulière.
- **Adéquation avec l'objectif du projet** : le jeu de données couvre un large éventail de pathologies chroniques (diabète, maladies cardiovasculaires, cancers, etc.), avec des indicateurs déclinés par État, par année et par catégorie démographique — ce qui correspond exactement au besoin d'analyse comparative visé par le projet.
- **Richesse dimensionnelle** : la présence de multiples axes d'analyse (temps, lieu, pathologie, stratification démographique, source) en fait un candidat naturel pour une modélisation en entrepôt de données, plutôt qu'un jeu de données plus étroit qui aurait limité les possibilités d'agrégation.
- **Accessibilité et format exploitable** : les données sont disponibles en accès libre au format CSV structuré, sans contrainte de licence bloquante pour un usage académique.

## 2. Choix du schéma de données : modélisation en étoile (Star Schema)

La base cible a été conçue selon un **schéma en étoile** classique (Kimball), avec six tables de dimension (`dim_time`, `dim_location`, `dim_topic`, `dim_question`, `dim_stratification`, `dim_data_source`) et deux tables de faits (`fact_disease_indicator`, `fact_risk_factor`).

**Justification :**
- **Adapté à un usage analytique** : contrairement à un schéma normalisé (3NF) optimisé pour les écritures transactionnelles, le schéma en étoile privilégie la simplicité des jointures et la performance en lecture — un critère décisif pour un entrepôt destiné à alimenter des tableaux de bord et des requêtes d'agrégation (via le dashboard du projet).
- **Lisibilité pour les utilisateurs métier** : la séparation claire entre faits mesurables (valeurs d'indicateurs, scores de risque) et dimensions descriptives (temps, lieu, pathologie...) facilite la compréhension du modèle par des analystes non techniques, et se prête naturellement à des outils de visualisation comme Power BI.
- **Deux tables de faits pour deux granularités d'usage** : `fact_disease_indicator` conserve la donnée brute au niveau le plus fin (par État, année, pathologie, stratification), tandis que `fact_risk_factor` stocke un indicateur dérivé et pré-calculé (score de risque normalisé sur 5 ans). Cette séparation évite de recalculer un agrégat coûteux à chaque requête analytique.
- **Contraintes d'unicité pour l'idempotence** : chaque table de dimension et de fait porte une contrainte `UNIQUE` sur sa clé naturelle, ce qui rend le chargement rejouable sans duplication — un choix qui découle directement du besoin d'un pipeline ETL fiable et ré-exécutable.
- **Cohérence avec les pratiques du domaine** : cette approche s'appuie sur les principes de modélisation dimensionnelle de Kimball, une référence éprouvée pour la conception d'entrepôts de données.

## 3. Choix des outils et scripts du pipeline ETL

Le pipeline d'extraction, transformation et chargement (ETL) a été développé en **Python**, avec **PostgreSQL** comme système de gestion de base de données cible, **pandas** pour la transformation tabulaire, et **psycopg2** pour l'interaction avec la base.

**Justification :**
- **PostgreSQL** : moteur open-source robuste, offrant un support natif des contraintes d'intégrité référentielle et des clauses `ON CONFLICT`, indispensables pour garantir l'idempotence du chargement sans logique applicative complexe.
- **pandas** : permet une manipulation efficace et lisible des données tabulaires (dédoublonnage, typage, jointures) lors des étapes de transformation, avec un écosystème mature et bien documenté.
- **psycopg2 + `execute_batch`** : le chargement en base utilise l'insertion par lots (`psycopg2.extras.execute_batch`) plutôt que des insertions ligne par ligne, ce qui réduit significativement le nombre d'allers-retours réseau sur des volumes de plusieurs dizaines de milliers de lignes.
- **Idempotence systématique (`ON CONFLICT DO NOTHING`)** : chaque insertion est conçue pour être rejouable sans erreur ni duplication, un choix structurant qui permet de relancer le pipeline à tout moment (après correction d'un bug ou ajout de nouvelles données) sans devoir purger la base au préalable.
- **Séparation des responsabilités par script** : le pipeline est découpé en trois scripts indépendants (`etl/extract`, `etl/transform`, `etl/load`), chacun responsable d'une seule étape. Ce découpage facilite les tests unitaires, le débogage ciblé, et la ré-exécution partielle du pipeline en cas de besoin.
- **Orchestration et vérification automatisées** : `run_pipeline.py` enchaîne les trois étapes sans intervention manuelle avec un comportement fail-fast, et `verify_pipeline.py` valide a posteriori l'absence de tables vides, de clés étrangères orphelines et d'écarts de volume — ce qui apporte une garantie de qualité reproductible à chaque exécution, plutôt qu'une vérification manuelle et ponctuelle.

## Synthèse

| Choix technique | Alternative écartée | Raison principale |
|---|---|---|
| Dataset CDC Chronic Disease Indicators | Données synthétiques ou jeu de données plus restreint | Source officielle, richesse dimensionnelle, adéquation avec l'analyse comparative visée |
| Schéma en étoile (Kimball) | Modèle normalisé (3NF) | Performance en lecture et lisibilité pour un usage analytique |
| PostgreSQL + pandas + psycopg2 | ORM complet (ex: SQLAlchemy) ou NoSQL | Contrôle fin des requêtes SQL, support natif de l'idempotence, simplicité pour un pipeline batch |
| Pipeline ETL modulaire et orchestré | Script monolithique unique | Maintenabilité, testabilité, ré-exécution partielle possible |

Ces choix reflètent une priorité donnée à la **fiabilité** (idempotence, vérification automatisée) et à la **simplicité analytique** (schéma en étoile), deux exigences centrales pour un entrepôt de données destiné à un usage décisionnel.