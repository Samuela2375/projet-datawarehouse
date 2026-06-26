-- =============================================================================
-- analytics/prevalence/by_demographics.sql
-- Prévalence par catégorie démographique (DIM_STRATIFICATION)
-- Distingue correctement chaque combinaison catégorie / valeur
-- Ex: Gender/Male, Gender/Female, Race/Hispanic, Race/White...
-- =============================================================================

SELECT
    ds.stratification_category              AS categorie,
    ds.stratification_value                 AS groupe,
    dt.topic_name                           AS maladie,
    ROUND(AVG(f.data_value), 2)             AS valeur_moyenne,
    COUNT(f.indicator_id)                   AS nb_mesures,
    ROUND(AVG(f.low_confidence_limit), 2)   AS ic_bas,
    ROUND(AVG(f.high_confidence_limit), 2)  AS ic_haut
FROM
    FACT_DISEASE_INDICATOR f
    JOIN DIM_STRATIFICATION ds ON f.stratification_id = ds.stratification_id
    JOIN DIM_TOPIC          dt ON f.topic_id           = dt.topic_id
WHERE
    f.data_value IS NOT NULL
    -- On exclut 'Overall' pour ne garder que les sous-groupes démographiques
    AND ds.stratification_category <> 'Overall'
GROUP BY
    ds.stratification_category,
    ds.stratification_value,
    dt.topic_name
ORDER BY
    ds.stratification_category,
    ds.stratification_value,
    valeur_moyenne DESC;