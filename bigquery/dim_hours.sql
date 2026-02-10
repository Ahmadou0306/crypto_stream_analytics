-- Utilise MERGE pour insérer seulement les heures manquantes
MERGE INTO crypto_analytics.dim_hours AS target
USING (
    WITH manually_array AS (
        SELECT GENERATE_ARRAY(0, 23, 1) as hour_generated
    ),

    unnest_hour_array AS (
        SELECT hours
        FROM manually_array,
        UNNEST(hour_generated) as hours
    ),

    hours_calculated AS (
        SELECT 
            hours,
            CASE
                WHEN hours = 0 THEN 12
                WHEN hours <= 12 THEN hours
                ELSE hours - 12
            END AS hour_12,

            CASE
                WHEN hours < 12 THEN 'AM'
                ELSE 'PM'
            END AS am_pm,

            CASE
                WHEN hours >= 6 AND hours <= 18 THEN TRUE
                ELSE FALSE
            END AS is_worked_hours,

            CASE
                WHEN (hours >= 7 AND hours < 10) OR (hours >= 16 AND hours < 19) THEN TRUE
                ELSE FALSE
            END AS is_rush_hour
        FROM unnest_hour_array    
    )

    SELECT * FROM hours_calculated
) AS source

-- Clé de matching : hours
ON target.hours = source.hours

-- Si l'heure n'existe pas, on l'insère
WHEN NOT MATCHED THEN
    INSERT (hours, hour_12, am_pm, is_worked_hours, is_rush_hour)
    VALUES (source.hours, source.hour_12, source.am_pm, source.is_worked_hours, source.is_rush_hour);