# Chronic Disease DWH

Entrepôt de données pour l'analyse des maladies chroniques les plus fréquentes aux États-Unis, basé sur le dataset officiel **U.S. Chronic Disease Indicators (CDI)** du CDC.

## Dataset
- Source : https://www.kaggle.com/datasets/cdc/chronic-disease
- À placer dans `data/raw/` (non versionné, voir `.gitignore`)

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
Le dataset source (`U.S. Chronic Disease Indicators`, CDC/Kaggle) est téléchargé en CSV et déposé dans `data/raw/`. C'est la seule étape manuelle du pipeline ; tout le reste est automatisé.

**Couche 2 — Intégration (ETL)**
Le module `etl/` est découpé en trois étapes successives, chacune indépendante :
- `etl/extract/` : lecture du CSV brut.
- `etl/transform/` : nettoyage (colonnes inutiles supprimées, `DataValue` converti en numérique, valeurs manquantes gérées, `GeoLocation` séparé en latitude/longitude, normalisation des noms d'États).
- `etl/load/` : insertion dans PostgreSQL, dimensions d'abord, table de faits ensuite.

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
| `data_value` | Valeur de l'indicateur |
| `data_value_type` | Type de valeur (taux brut, ajusté à l'âge…) |
| `low_confidence_limit` / `high_confidence_limit` | Intervalle de confiance |

Une seconde table de faits, `FACT_RISK_FACTOR`, croise les indicateurs avec un score de risque par État (usage prédictif).

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
DIM_TIME -------------|
DIM_LOCATION ---------|
DIM_TOPIC -------------|---- FACT_DISEASE_INDICATOR ---- FACT_RISK_FACTOR
DIM_QUESTION ----------|
DIM_STRATIFICATION ----|
DIM_DATA_SOURCE -------|
```

Ce choix de schéma en étoile (plutôt qu'un schéma normalisé classique) privilégie la simplicité des jointures pour les requêtes analytiques et la compatibilité directe avec Power BI.

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
chronic-disease-dwh/
├── data/          # Données brutes, nettoyées, exports, rapports
├── etl/           # Scripts d'extraction, transformation, chargement
├── warehouse/     # Schéma SQL, requêtes, migrations
├── analytics/     # Analyses : prévalence, prévisions, classification de risque
├── api/           # API (controllers, services, routes) — optionnel
├── dashboard/      # Fichiers Power BI / exports dashboard
├── docker/         # Conteneurisation (optionnel)
└── docs/           # Documentation, rapport, mémoire
```

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

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
cp .env.example .env  # puis renseigner les valeurs
```

## Pipeline ETL

```bash
python etl/extract/extract.py
python etl/transform/transform.py
python etl/load/load.py
```

## Base de données

Le schéma (Star Schema) est disponible dans `warehouse/schema/schema.sql`.

## Avancement

- [ ] Extraction des données
- [ ] Nettoyage / transformation
- [ ] Création du schéma PostgreSQL
- [ ] Chargement des dimensions
- [ ] Chargement de la table de faits
- [ ] Requêtes d'analyse
- [ ] Dashboard Power BI
- [ ] Rapport final