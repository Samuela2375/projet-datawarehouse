# Chronic Disease DWH

Entrepôt de données pour l'analyse des maladies chroniques les plus fréquentes aux États-Unis, basé sur le dataset officiel **U.S. Chronic Disease Indicators (CDI)** du CDC.

## Dataset

- Source : [U.S. Chronic Disease Indicators (CDI)](https://www.kaggle.com/datasets/cdc/chronic-disease) — CDC / Kaggle
- Fichier attendu : `U.S._Chronic_Disease_Indicators.csv` (~117 Mo)
- **Le fichier est suivi via Git LFS et récupéré automatiquement au clonage** (voir section [Cloner ce projet](#cloner-ce-projet-git-lfs-requis)) — aucune action manuelle de téléchargement/placement n'est nécessaire si Git LFS est bien installé.
- Emplacement dans le dépôt : `data/raw/U.S._Chronic_Disease_Indicators.csv` **à la racine du dépôt**, en dehors du dossier `chronic-disease-dwh/` (voir structure ci-dessous).

## Architecture globale

Le projet suit une architecture classique d'entrepôt de données en 5 couches :

```
                    +----------------------+
                    | Sources de données  |
                    +----------------------+
                     /        |         \
                    /         |          \
            Indicateurs   Données      Données
            de maladies   démographiques  géographiques
            (CDC/Kaggle)  (Stratification) (GeoLocation)
                    \         |          /
                     \        |         /
                    +------------------+
                    |   ETL / ELT      |
                    +------------------+
                              |
                              v
                    +----------------------+
                    |   Data Warehouse     |
                    |     PostgreSQL       |
                    +----------------------+
                       /              \
                      v                v
                 Analyse BI       Dashboards
                 Statistique       Power BI
```

**Couche 1 — Acquisition**
Le dataset source (`U.S. Chronic Disease Indicators`, CDC/Kaggle) est versionné via Git LFS et récupéré dans `data/raw/` dès le clonage. C'est la seule étape « externe » du pipeline ; tout le reste est automatisé.

**Couche 2 — Intégration (ETL)**
Le module `etl/` est découpé en trois étapes successives, chacune indépendante :
- `etl/extract/` : lecture du CSV brut, validation des colonnes, génération d'un dictionnaire de données (`docs/dictionnaire_donnees.md`).
- `etl/transform/` : nettoyage (colonnes inutiles supprimées, `DataValue` converti en numérique, valeurs manquantes gérées, `GeoLocation` séparé en latitude/longitude, normalisation des noms d'États et des topics) → export vers `data/cleaned/chronic_disease_cleaned.csv`.
- `etl/load/` : insertion idempotente dans PostgreSQL (dimensions d'abord, table de faits ensuite, `ON CONFLICT DO NOTHING`).

**Couche 3 — Stockage (Data Warehouse)**
Modélisation en **schéma en étoile** dans PostgreSQL (détails ci-dessous), définie dans `warehouse/schema/`.

**Couche 4 — Intelligence**
Requêtes SQL et scripts d'analyse dans `analytics/` (prévalence, prévisions, classification de risque).

**Couche 5 — Visualisation**
Dashboard Power BI alimenté directement sur la base PostgreSQL, fichiers de référence dans `dashboard/`.

### Modèle de données (schéma en étoile)

**Table de faits — `FACT_DISEASE_INDICATOR`**

| Champ | Description |
|---|---|
| `indicator_id` | ID mesure unique (PK) |
| `time_id` | FK → `DIM_TIME` |
| `location_id` | FK → `DIM_LOCATION` |
| `topic_id` | FK → `DIM_TOPIC` |
| `question_id` | FK → `DIM_QUESTION` |
| `stratification_id` | FK → `DIM_STRATIFICATION` |
| `source_id` | FK → `DIM_DATA_SOURCE` (nullable) |
| `data_value` | Valeur de l'indicateur |
| `data_value_type` | Type de valeur (taux brut, ajusté à l'âge…) |
| `low_confidence_limit` / `high_confidence_limit` | Intervalle de confiance |

Une seconde table de faits, `FACT_RISK_FACTOR`, croise `location_id`, `time_id` et `topic_id` avec un score de risque normalisé (0–100), calculé en SQL à partir des 5 dernières années disponibles.

**Tables de dimensions**

| Table | Contenu |
|---|---|
| `DIM_TIME` | `year_start`, `year_end` |
| `DIM_LOCATION` | État/territoire, `latitude`, `longitude` |
| `DIM_TOPIC` | Catégorie de pathologie (17 catégories), niveau de risque |
| `DIM_QUESTION` | Libellé précis de l'indicateur, lié à `DIM_TOPIC` |
| `DIM_STRATIFICATION` | Catégorie démographique (sexe, origine…) et valeur |
| `DIM_DATA_SOURCE` | Source de la donnée (BRFSS, NVSS, USCS) |

```
DIM_TIME --------------|
DIM_LOCATION ----------|
DIM_TOPIC --------------|---- FACT_DISEASE_INDICATOR ---- FACT_RISK_FACTOR
DIM_QUESTION -----------|
DIM_STRATIFICATION -----|
DIM_DATA_SOURCE --------|
```

Ce choix de schéma en étoile (plutôt qu'un schéma normalisé classique) privilégie la simplicité des jointures pour les requêtes analytiques et la compatibilité directe avec Power BI. Le détail des justifications techniques est disponible dans [`docs/choix_techniques.md`](chronic-disease-dwh/docs/choix_techniques.md).

### Flux opérationnel

```
Indicateur publié par le CDC (CSV)
        |
        v
Pipeline ETL extrait les données
        |
        v
Chargement dans le Data Warehouse
        |
        v
Dashboard actualise les statistiques
        |
        v
Analyse et détection des pathologies dominantes
```

## Structure du projet

```
projet-datawarehouse/                 # racine du dépôt Git
├── data/
│   └── raw/                          # CSV brut (Git LFS) — U.S._Chronic_Disease_Indicators.csv
├── run_pipeline.py                   # orchestrateur : extraction -> transformation -> chargement
├── verify_pipeline.py                # vérification post-chargement (tables, FK, volumes)
├── entrepot_donnees_CDC.pdf
├── README.md
└── chronic-disease-dwh/              # code du projet
    ├── data/
    │   ├── cleaned/                  # CSV nettoyé produit par etl/transform/
    │   ├── exports/                  # résultats CSV des analyses (analytics/)
    │   └── reports/
    ├── etl/                          # extraction, transformation, chargement
    │   ├── extract/
    │   ├── transform/
    │   └── load/
    ├── warehouse/                    # schéma SQL, requêtes, migrations
    │   └── schema/schema.sql
    ├── analytics/                    # prévalence, prévisions, classification de risque
    ├── api/                          # API (controllers, services, routes) — optionnel
    ├── dashboard/                    # fichier Power BI (.pbix)
    ├── docker/                       # conteneurisation (optionnel)
    ├── docs/                         # documentation, choix techniques, rapport
    ├── .env / .env.example
    └── requirements.txt
```

> ⚠️ **Point d'attention** : les données brutes (`data/raw/`) vivent à la **racine du dépôt**, tandis que les données nettoyées, les exports et le code vivent **dans `chronic-disease-dwh/`**. C'est voulu (le brut est versionné une seule fois pour tout le repo), mais c'est la source de confusion la plus fréquente pour un nouvel arrivant — vérifiez bien dans quel dossier vous vous trouvez avant de lancer une commande.

## Cloner ce projet (Git LFS requis)

Le dataset CSV (`U.S._Chronic_Disease_Indicators.csv`, ~117 Mo) dépasse la limite de fichier de GitHub et est donc suivi via **Git LFS**. Sans Git LFS installé, ce fichier sera vide ou remplacé par un simple pointeur texte après clonage.

**1. Installer Git LFS (une seule fois par machine)**

Windows :
```cmd
winget install GitHub.GitLFS
```

macOS :
```bash
brew install git-lfs
```

Linux (Debian/Ubuntu) :
```bash
sudo apt install git-lfs
```

**2. Activer Git LFS (une seule fois par machine)**

```bash
git lfs install
```

**3. Cloner le dépôt**

```bash
git clone https://github.com/Samuela2375/projet-datawarehouse.git
cd projet-datawarehouse
```

**4. Vérifier que le CSV est bien récupéré en entier**

```bash
git lfs ls-files
```

Si le fichier semble anormalement petit (quelques Ko au lieu de ~117 Mo) :
```bash
git lfs pull
```

**Si vous avez déjà cloné le dépôt avant l'activation de Git LFS**, pas besoin de re-cloner :
```bash
git lfs install
git pull
git lfs pull
```

## Installation

Prérequis : Python 3.13, PostgreSQL 16 (ou compatible), Git LFS déjà configuré (étape précédente).

```bash
cd chronic-disease-dwh
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
cp .env.example .env      # puis renseigner les valeurs (voir ci-dessous)
```

**Variables à renseigner dans `chronic-disease-dwh/.env`** :

| Variable | Description | Exemple |
|---|---|---|
| `DB_HOST` | Hôte PostgreSQL | `localhost` |
| `DB_PORT` | Port PostgreSQL | `5432` |
| `DB_NAME` | Nom de la base | `chronic_disease_dwh` |
| `DB_USER` | Utilisateur PostgreSQL | `postgres` |
| `DB_PASSWORD` | Mot de passe de l'utilisateur | *(votre mot de passe local)* |

## Créer la base de données et le schéma

Ces deux étapes sont **manuelles** et doivent être faites une seule fois avant le premier chargement (vous aurez besoin de votre mot de passe PostgreSQL) :

```bash
# Toujours depuis chronic-disease-dwh/
createdb -U postgres chronic_disease_dwh
psql -U postgres -d chronic_disease_dwh -f warehouse/schema/schema.sql
```

## Pipeline ETL

### Option recommandée — exécution automatisée

Depuis la **racine du dépôt** (`projet-datawarehouse/`, PAS `chronic-disease-dwh/`) :

```bash
python run_pipeline.py
```

Ce script enchaîne automatiquement, sans intervention manuelle :
1. `etl/extract/extract.py` — lecture du CSV brut, validation, dictionnaire de données
2. `etl/transform/transform.py` — nettoyage, export du CSV nettoyé
3. `etl/load/load.py` — chargement idempotent dans PostgreSQL

Le script s'arrête proprement dès qu'une étape échoue (comportement *fail-fast*) et retourne un code de sortie non nul en cas d'erreur.

Une fois le pipeline terminé, validez le résultat avec :

```bash
python verify_pipeline.py
```

Ce script contrôle : la présence de données dans les 7 tables attendues, l'absence de clés étrangères orphelines, et la cohérence des volumes entre le CSV nettoyé et la table de faits. Il se termine par `Vérification RÉUSSIE` (code `0`) ou liste les échecs en détail (code `1`).

### Option manuelle — étape par étape

Utile pour déboguer une étape en particulier. Toujours depuis `chronic-disease-dwh/` :

```bash
python etl/extract/extract.py
python etl/transform/transform.py
python etl/load/load.py
```

## Base de données

Le schéma (Star Schema) est disponible dans `chronic-disease-dwh/warehouse/schema/schema.sql`.

## Avancement

- [x] Extraction des données
- [x] Nettoyage / transformation
- [x] Création du schéma PostgreSQL
- [x] Chargement des dimensions
- [x] Chargement de la table de faits
- [x] Requêtes d'analyse
- [x] Dashboard Power BI
- [ ] Rapport

## Analytics

Les scripts d'analyse sont dans `chronic-disease-dwh/analytics/`.

### Prérequis
Avant de lancer les analyses, le pipeline ETL doit avoir été exécuté complètement
(extraction → transformation → chargement), et validé via `verify_pipeline.py`.

### Structure des fichiers
```
analytics/
├── run_analytics.py                    # Script principal
├── utils.py                            # Fonctions partagées
├── prevalence/
│   ├── top_diseases.sql                # Top 10 maladies
│   ├── by_state.sql                    # Prévalence par État
│   └── by_demographics.sql             # Prévalence par démographie
├── forecasting/
│   └── time_evolution.sql              # Évolution par année
└── risk_classification/
    └── classify_states.py              # Classification K-Means
```

### Lancer toutes les analyses

```bash
cd chronic-disease-dwh
python -m analytics.run_analytics
```

Les résultats CSV sont exportés dans `data/exports/`.

### Tester la syntaxe Python uniquement

```bash
python -m py_compile analytics/utils.py
python -m py_compile analytics/risk_classification/classify_states.py
python -m py_compile analytics/run_analytics.py
```

Aucun message = pas d'erreur ✓

### Résultats exportés

| Fichier CSV | Contenu |
|---|---|
| `data/exports/prevalence/top_diseases.csv` | Top 10 maladies |
| `data/exports/prevalence/by_state.csv` | Prévalence par État |
| `data/exports/prevalence/by_demographics.csv` | Prévalence par démographie |
| `data/exports/forecasting/time_evolution.csv` | Évolution temporelle |
| `data/exports/risk_classification/clusters_etats.csv` | Clusters K-Means |

## 📊 Guide de test — Couche restitution (Power BI)

Ce guide explique comment tester et valider le tableau de bord Power BI développé pour la restitution et l'analyse des données de santé.

### 1. Prérequis
* **Power BI Desktop** installé sur votre machine.
* La base de données PostgreSQL du Data Warehouse active, avec les données chargées **et** les tables d'analytics alimentées (`python -m analytics.run_analytics`).

### 2. Emplacement du fichier
`chronic-disease-dwh/dashboard/chronic_disease_dashboard.pbix`

### 3. Protocole de test

1. **Ouverture du dashboard :**
   * N'ouvrez pas le fichier depuis votre éditeur de code (VS Code afficherait une erreur de fichier binaire).
   * Ouvrez l'Explorateur de fichiers (le dossier jaune classique).
   * Naviguez vers `projet-datawarehouse/chronic-disease-dwh/dashboard/`.
   * Double-cliquez sur `chronic_disease_dashboard.pbix` pour lancer Power BI Desktop.

2. **Actualisation des données (si nécessaire) :**
   * Si vos identifiants PostgreSQL locaux diffèrent, allez dans **Accueil** → **Transformer les données** → **Paramètres de la source de données**.
   * Modifiez les informations d'identification pour pointer vers votre instance locale, puis cliquez sur **Actualiser**.

3. **Validation des visuels :**
   * **KPIs** : vérifiez que les cartes de performance affichent correctement les volumes globaux.
   * **Top 10** : manipulez l'histogramme pour valider le classement des pathologies.
   * **Analyse temporelle** : utilisez la courbe chronologique pour observer l'évolution des données.
   * **Filtres croisés** : cliquez sur un élément d'un graphique et vérifiez que les autres visuels s'actualisent dynamiquement.

4. **Conformité des données :**
   * Les chiffres affichés doivent être strictement alignés avec les résultats des requêtes SQL d'`analytics/`.
   * Le typage des coordonnées géographiques (latitude/longitude) via Power Query a été validé et ne bloque plus le modèle.

## Dépannage — problèmes courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `FileNotFoundError` sur `extract.py`/`transform.py`/`load.py` | Commande lancée depuis le mauvais dossier | `run_pipeline.py`/`verify_pipeline.py` se lancent depuis la **racine du dépôt** ; les scripts `etl/*.py` individuels se lancent depuis `chronic-disease-dwh/` |
| Le CSV brut fait quelques Ko au lieu de ~117 Mo | Git LFS non installé/activé avant le clone | `git lfs install` puis `git lfs pull` (voir [Cloner ce projet](#cloner-ce-projet-git-lfs-requis)) |
| `psycopg2.OperationalError: connection refused` | PostgreSQL non démarré, ou `.env` mal renseigné | Vérifier que le service PostgreSQL tourne et que `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD` dans `chronic-disease-dwh/.env` sont corrects |
| `relation "..." does not exist` au chargement | Schéma non créé avant le chargement | Exécuter `createdb` puis `psql -f warehouse/schema/schema.sql` (voir [Créer la base de données et le schéma](#créer-la-base-de-données-et-le-schéma)) |
| `verify_pipeline.py` signale des tables vides ou des FK orphelines | Pipeline interrompu avant la fin, ou base partiellement chargée | Relancer `python run_pipeline.py` — les insertions sont idempotentes (`ON CONFLICT DO NOTHING`), aucun risque de doublon |
| Écart de volume signalé par `verify_pipeline.py` proche de 1 % | Normal dans une certaine mesure : des lignes du CSV sont ignorées si une dimension ne peut être résolue (voir logs de `load.py`) | Vérifier dans les logs du chargement le détail des lignes ignorées ; un écart < 1 % est attendu et accepté |