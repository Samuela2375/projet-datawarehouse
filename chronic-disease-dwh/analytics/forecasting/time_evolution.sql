-- =============================================================================
-- analytics/forecasting/time_evolution.sql
-- Évolution temporelle des maladies chroniques
-- Retourne 1 ligne par année, triée chronologiquement (ASC)
-- =============================================================================

SELECT
    ti.year_start                           AS annee,
    dt.topic_name                           AS maladie,
    ROUND(AVG(f.data_value), 2)             AS valeur_moyenne,
    COUNT(f.indicator_id)                   AS nb_mesures,
    ROUND(AVG(f.low_confidence_limit), 2)   AS ic_bas,
    ROUND(AVG(f.high_confidence_limit), 2)  AS ic_haut
FROM
    FACT_DISEASE_INDICATOR f
    JOIN DIM_TIME            ti ON f.time_id           = ti.time_id
    JOIN DIM_TOPIC           dt ON f.topic_id           = dt.topic_id
    JOIN DIM_STRATIFICATION  ds ON f.stratification_id  = ds.stratification_id
WHERE
    f.data_value IS NOT NULL
    AND ds.stratification_category = 'Overall'
GROUP BY
    ti.year_start,
    dt.topic_name
ORDER BY
    ti.year_start ASC,
    dt.topic_name ASC;