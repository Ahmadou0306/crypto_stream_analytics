INSERT INTO crypto_analytics.dim_symboles(
    symbol,
    symbole_libelle,
    devise_cotation,
    devise_cotation_nom
)

WITH symboles_distincts AS (
    SELECT DISTINCT symbol
    FROM crypto_raw.historical_raw
),

symboles_enrichis AS (
    SELECT 
        symbol,
        CASE 
            WHEN symbol = 'BTCUSDT' THEN 'Bitcoin'
            WHEN symbol = 'ETHUSDT' THEN 'Ethereum'
            WHEN symbol = 'SOLUSDT' THEN 'Solana'
            ELSE 'Autres'
        END AS symbole_libelle,
        'USDT' AS devise_cotation,
        'Tether' AS devise_cotation_nom
    FROM symboles_distincts
)

SELECT *
FROM symboles_enrichis;