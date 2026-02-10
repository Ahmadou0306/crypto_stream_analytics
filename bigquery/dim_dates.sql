INSERT INTO crypto_analytics.dim_dates(
    date,
    year,
    month,
    month_name,
    day,
    day_of_week,
    day_of_week_name
)

WITH dates_array AS (
    SELECT 
        GENERATE_DATE_ARRAY(
            DATE('2020-01-01'),
            CURRENT_DATE,
            INTERVAL 1 DAY
        ) AS date_array_generated
),

dates_table AS (
    SELECT date
    FROM dates_array,
    UNNEST(date_array_generated) AS date
),

date_calcule AS (
    SELECT 
        date,
        EXTRACT(YEAR FROM date) AS year,
        EXTRACT(MONTH FROM date) AS month,
        FORMAT_DATE('%B', date) AS month_name,
        EXTRACT(DAY FROM date) AS day,
        EXTRACT(DAYOFWEEK FROM date) AS day_of_week,
        FORMAT_DATE('%A', date) AS day_of_week_name
    FROM dates_table
)

SELECT *
FROM date_calcule
ORDER BY date ASC;