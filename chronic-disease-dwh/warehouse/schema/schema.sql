-- =========================================
-- Schéma : Chronic Disease Data Warehouse
-- Star Schema basé sur U.S. Chronic Disease Indicators (CDC)
-- =========================================

-- Dimensions
CREATE TABLE DIM_TIME (
    time_id SERIAL PRIMARY KEY,
    year_start INT NOT NULL,
    year_end INT NOT NULL
);

CREATE TABLE DIM_LOCATION (
    location_id SERIAL PRIMARY KEY,
    location_abbr VARCHAR(10) NOT NULL,
    location_desc VARCHAR(100) NOT NULL,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6)
);

CREATE TABLE DIM_TOPIC (
    topic_id SERIAL PRIMARY KEY,
    topic_name VARCHAR(150) NOT NULL,
    is_chronic BOOLEAN DEFAULT TRUE,
    risk_level VARCHAR(50)
);

CREATE TABLE DIM_QUESTION (
    question_id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    topic_id INT REFERENCES DIM_TOPIC(topic_id)
);

CREATE TABLE DIM_STRATIFICATION (
    stratification_id SERIAL PRIMARY KEY,
    stratification_category VARCHAR(100),
    stratification_value VARCHAR(100)
);

CREATE TABLE DIM_DATA_SOURCE (
    source_id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL
);

-- Table de faits principale
CREATE TABLE FACT_DISEASE_INDICATOR (
    indicator_id SERIAL PRIMARY KEY,
    time_id INT REFERENCES DIM_TIME(time_id),
    location_id INT REFERENCES DIM_LOCATION(location_id),
    topic_id INT REFERENCES DIM_TOPIC(topic_id),
    question_id INT REFERENCES DIM_QUESTION(question_id),
    stratification_id INT REFERENCES DIM_STRATIFICATION(stratification_id),
    source_id INT REFERENCES DIM_DATA_SOURCE(source_id),
    data_value DECIMAL(12,2),
    data_value_type VARCHAR(100),
    low_confidence_limit DECIMAL(12,2),
    high_confidence_limit DECIMAL(12,2)
);

-- Table de faits complémentaire
CREATE TABLE FACT_RISK_FACTOR (
    risk_id SERIAL PRIMARY KEY,
    location_id INT REFERENCES DIM_LOCATION(location_id),
    time_id INT REFERENCES DIM_TIME(time_id),
    topic_id INT REFERENCES DIM_TOPIC(topic_id),
    risk_score DECIMAL(6,2)
);

-- Index utiles
CREATE INDEX idx_fact_topic ON FACT_DISEASE_INDICATOR(topic_id);
CREATE INDEX idx_fact_location ON FACT_DISEASE_INDICATOR(location_id);
CREATE INDEX idx_fact_time ON FACT_DISEASE_INDICATOR(time_id);
