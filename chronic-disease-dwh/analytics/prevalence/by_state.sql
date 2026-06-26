-- =============================================================================
-- analytics/prevalence/by_state.sql
-- Prévalence moyenne par État (1 ligne par État de DIM_LOCATION)
-- Retourne un résultat par État, trié par valeur décroissante
-- =============================================================================

SELECT
    dl.location_abbr                        AS code_etat,
    dl.location_desc                        AS nom_etat,
    dl.latitude,
    dl.longitude,
    ROUND(AVG(f.data_value), 2)             AS valeur_moyenne,
    COUNT(f.indicator_id)                   AS nb_mesures,
    ROUND(AVG(f.low_confidence_limit), 2)   AS ic_bas,
    ROUND(AVG(f.high_confidence_limit), 2)  AS ic_haut
FROM
    FACT_DISEASE_INDICATOR f
    JOIN DIM_LOCATION        dl ON f.location_id      = dl.location_id
    JOIN DIM_STRATIFICATION  ds ON f.stratification_id = ds.stratification_id
WHERE
    f.data_value IS NOT NULL
    AND ds.stratification_category = 'Overall'
GROUP BY
    dl.location_id,
    dl.location_abbr,
    dl.location_desc,
    dl.latitude,
    dl.longitude
ORDER BY
    valeur_moyenne DESC;