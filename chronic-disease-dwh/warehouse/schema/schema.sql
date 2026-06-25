-- =========================================
-- Schéma : Chronic Disease Data Warehouse
-- Star Schema basé sur U.S. Chronic Disease Indicators (CDC)
-- =========================================

-- Dimensions
CREATE TABLE DIM_TIME (
    time_id SERIAL PRIMARY KEY,
    year_start INT NOT NULL,
    year_end INT NOT NULL
);-- =============================================================================
-- Entrepôt de données — Maladies chroniques (CDC)
-- warehouse/schema/schema.sql
-- Schéma en étoile (Star Schema) — PostgreSQL
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Nettoyage (idempotent)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_risk_factor        CASCADE;
DROP TABLE IF EXISTS fact_disease_indicator  CASCADE;
DROP TABLE IF EXISTS dim_data_source         CASCADE;
DROP TABLE IF EXISTS dim_stratification      CASCADE;
DROP TABLE IF EXISTS dim_question            CASCADE;
DROP TABLE IF EXISTS dim_topic               CASCADE;
DROP TABLE IF EXISTS dim_location            CASCADE;
DROP TABLE IF EXISTS dim_time                CASCADE;

-- =============================================================================
-- DIMENSIONS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- DIM_TIME
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_TIME (
    time_id SERIAL PRIMARY KEY,
    year_start INT NOT NULL,
    year_end INT NOT NULL,
    CONSTRAINT uq_dim_time UNIQUE (year_start, year_end)
);

CREATE INDEX idx_dim_time_year_start ON DIM_TIME (year_start);

-- -----------------------------------------------------------------------------
-- DIM_LOCATION
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_LOCATION (
    location_id SERIAL PRIMARY KEY,
    location_abbr VARCHAR(10) NOT NULL,
    location_desc VARCHAR(100) NOT NULL,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    CONSTRAINT uq_dim_location UNIQUE (location_abbr)
);

CREATE INDEX idx_dim_location_abbr ON DIM_LOCATION (location_abbr);

-- -----------------------------------------------------------------------------
-- DIM_TOPIC
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_TOPIC (
    topic_id SERIAL PRIMARY KEY,
    topic_name VARCHAR(150) NOT NULL,
    is_chronic BOOLEAN DEFAULT TRUE,
    risk_level VARCHAR(50)   CHECK (risk_level IN ('Low', 'Medium', 'High')),
    CONSTRAINT uq_dim_topic UNIQUE (topic_name)
);

-- -----------------------------------------------------------------------------
-- DIM_QUESTION
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_QUESTION (
    question_id   SERIAL        PRIMARY KEY,
    question_text TEXT          NOT NULL,
    topic_id      INT           NOT NULL REFERENCES DIM_TOPIC (topic_id)
                                    ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT uq_dim_question UNIQUE (question_text)
);

CREATE INDEX idx_dim_question_topic ON DIM_QUESTION (topic_id);

-- -----------------------------------------------------------------------------
-- DIM_STRATIFICATION
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_STRATIFICATION (
    stratification_id       SERIAL        PRIMARY KEY,
    stratification_category VARCHAR(100)  NOT NULL,   -- ex: 'Gender', 'Race/Ethnicity', 'Overall'
    stratification_value    VARCHAR(100)  NOT NULL,   -- ex: 'Male', 'Hispanic', 'Overall'
    CONSTRAINT uq_dim_stratification UNIQUE (stratification_category, stratification_value)
);

-- -----------------------------------------------------------------------------
-- DIM_DATA_SOURCE
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_DATA_SOURCE (
    source_id   SERIAL       PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,   -- ex: 'BRFSS', 'NVSS', 'USCS'
    CONSTRAINT uq_dim_data_source UNIQUE (source_name)
);

-- =============================================================================
-- TABLES DE FAITS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FACT_DISEASE_INDICATOR  (table de faits principale)
-- -----------------------------------------------------------------------------
CREATE TABLE FACT_DISEASE_INDICATOR (
    indicator_id           SERIAL     PRIMARY KEY,
    time_id                INT           NOT NULL REFERENCES DIM_TIME          (time_id),
    location_id            INT           NOT NULL REFERENCES DIM_LOCATION      (location_id),
    topic_id               INT           NOT NULL REFERENCES DIM_TOPIC         (topic_id),
    question_id            INT           NOT NULL REFERENCES DIM_QUESTION      (question_id),
    stratification_id      INT           NOT NULL REFERENCES DIM_STRATIFICATION(stratification_id),
    source_id              INT                    REFERENCES DIM_DATA_SOURCE   (source_id),

    data_value             DECIMAL(12, 2),
    data_value_type        VARCHAR(100),          -- ex: 'Crude Rate', 'Age-adjusted Rate'
    low_confidence_limit   DECIMAL(12, 2),
    high_confidence_limit  DECIMAL(12, 2),

    -- Clé de déduplication : évite les doublons si le script est relancé
    CONSTRAINT uq_fact_disease_indicator UNIQUE (
        time_id, location_id, topic_id, question_id, stratification_id, data_value_type
    )
);

CREATE INDEX idx_fdi_time          ON fact_disease_indicator (time_id);
CREATE INDEX idx_fdi_location      ON fact_disease_indicator (location_id);
CREATE INDEX idx_fdi_topic         ON fact_disease_indicator (topic_id);
CREATE INDEX idx_fdi_question      ON fact_disease_indicator (question_id);
CREATE INDEX idx_fdi_stratif       ON fact_disease_indicator (stratification_id);

-- -----------------------------------------------------------------------------
-- FACT_RISK_FACTOR  (table de faits complémentaire — usage prédictif)
--
-- Formule du risk_score (documentée ici et dans le code ETL) :
--
--   risk_score = AVG(data_value) sur les 5 dernières années disponibles
--                pour la combinaison (location_id, topic_id),
--                normalisé sur 100 par rapport au MAX national.
--
--   risk_score = ROUND(
--                  100 * avg_recent / MAX(avg_recent) OVER (PARTITION BY topic_id),
--                2)
--
-- Interprétation : 100 = État le plus touché pour cette pathologie ;
--                    0 = aucune donnée ou valeur nulle.
-- -----------------------------------------------------------------------------
CREATE TABLE FACT_RISK_FACTOR (
    risk_id     SERIAL  PRIMARY KEY,
    location_id INT        NOT NULL REFERENCES DIM_LOCATION (location_id),
    time_id     INT        NOT NULL REFERENCES DIM_TIME     (time_id),
    topic_id    INT        NOT NULL REFERENCES DIM_TOPIC    (topic_id),
    risk_score  DECIMAL(6, 2),          -- valeur entre 0 et 100
    CONSTRAINT uq_fact_risk_factor UNIQUE (location_id, time_id, topic_id)
);

CREATE INDEX idx_fact_location ON FACT_DISEASE_INDICATOR (location_id);
CREATE INDEX idx_fact_topic    ON FACT_DISEASE_INDICATOR (topic_id);
CREATE INDEX idx_fact_time     ON FACT_DISEASE_INDICATOR (time_id);