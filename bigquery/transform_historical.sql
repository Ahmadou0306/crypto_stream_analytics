-- Insérer l'historique transformé dans la table finale
INSERT INTO crypto_analytics.market_data_unified (
    timestamp,
    date,
    hour,
    day_of_week,
    symbol,
    open,
    high,
    low,
    close,
    volume,
    trades,
    sma_20,
    ema_50,
    rsi_14,
    macd,
    macd_signal,
    bb_upper,
    bb_middle,
    bb_lower,
    source,
    ingestion_timestamp
)
WITH cleaned AS (
  SELECT 
    TIMESTAMP(open_time) AS timestamp,
    DATE(open_time) AS date,
    EXTRACT(HOUR FROM TIMESTAMP(open_time)) AS hour,
    FORMAT_DATE('%A', DATE(open_time)) AS day_of_week,
    symbol,
    open,
    high,
    low,
    close,
    volume,
    trades
  FROM crypto_analytics.historical_raw
  WHERE 
    open IS NOT NULL
    AND close IS NOT NULL
    AND volume > 0
),

price_changes AS (
  SELECT 
    *,
    close - LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp) AS price_change
  FROM cleaned
),

gains_losses AS (
  SELECT 
    *,
    CASE WHEN price_change > 0 THEN price_change ELSE 0 END AS gain,
    CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END AS loss
  FROM price_changes
),

avg_gains_losses AS (
  SELECT 
    *,
    AVG(gain) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
    ) AS avg_gain,
    AVG(loss) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 13 PRECEDING AND CURRENT ROW -- pour 14 périodes 
    ) AS avg_loss
  FROM gains_losses
),

rsi_calc AS (
  SELECT 
    *,
    CASE 
      WHEN avg_loss = 0 THEN 100
      ELSE 100 - (100 / (1 + (avg_gain / avg_loss)))
    END AS rsi_14
  FROM avg_gains_losses
),

-- Calcul EMA 12 et EMA 26 pour MACD
ema_calculation AS (
  SELECT 
    *,
    -- EMA 12 (approximation avec moyenne pondérée)
    AVG(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS ema_12,
    
    -- EMA 26
    AVG(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 25 PRECEDING AND CURRENT ROW
    ) AS ema_26
  FROM rsi_calc
),

macd_calculation AS (
  SELECT 
    *,
    ema_12 - ema_26 AS macd,
    AVG(ema_12 - ema_26) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 8 PRECEDING AND CURRENT ROW
    ) AS macd_signal
  FROM ema_calculation
)

indicateur_calcule AS (
  SELECT 
    *,
    -- SMA 20
    AVG(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS sma_20,
    
    -- EMA 50
    AVG(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
    ) AS ema_50,
        
    -- Bollinger Bands
    AVG(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS bb_middle,
    
    STDDEV(close) OVER (
      PARTITION BY symbol 
      ORDER BY timestamp 
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS bb_stddev
    
  FROM macd_calculation
)

SELECT 
  timestamp,
  date,
  hour,
  day_of_week,
  symbol,
  open,
  high,
  low,
  close,
  volume,
  trades,

  sma_20,
  ema_50,
  rsi_14,
  macd,
  macd_signal,
  bb_middle + (2 * bb_stddev) AS bb_upper,
  bb_middle,
  bb_middle - (2 * bb_stddev) AS bb_lower,
  'historical' AS source,
  CURRENT_TIMESTAMP() AS ingestion_timestamp
FROM indicateur_calcule;