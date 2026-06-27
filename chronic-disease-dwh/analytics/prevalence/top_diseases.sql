-- =============================================================================
-- analytics/prevalence/top_diseases.sql
-- Top 10 maladies chroniques par valeur moyenne décroissante
-- Retourne exactement 10 lignes triées par data_value DESC
-- =============================================================================

SELECT
    dt.topic_name                           AS maladie,
    ROUND(AVG(f.data_value), 2)             AS valeur_moyenne,
    COUNT(f.indicator_id)                   AS nb_mesures,
    ROUND(AVG(f.low_confidence_limit), 2)   AS ic_bas,
    ROUND(AVG(f.high_confidence_limit), 2)  AS ic_haut
FROM
    FACT_DISEASE_INDICATOR f
    JOIN DIM_TOPIC       dt ON f.topic_id    = dt.topic_id
    JOIN DIM_STRATIFICATION ds ON f.stratification_id = ds.stratification_id
WHERE
    f.data_value IS NOT NULL
    -- On garde uniquement la strate globale pour comparer les maladies à égalité
    AND ds.stratification_category = 'Overall'
GROUP BY
    dt.topic_name
ORDER BY
    valeur_moyenne DESC
LIMIT 10;