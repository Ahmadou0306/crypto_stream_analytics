import apache_beam as beam
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CalculateIndicators(beam.DoFn):
    
    def __init__(self):
        self.errors_count = 0
    
    def process(self, element):
        try:
            symbol, rows = element
            sorted_rows = sorted(rows, key=lambda x: x['timestamp'])
            
            logger.info(
                f"Début calcul indicateurs pour {symbol}",
                extra={
                    'symbol': symbol,
                    'nb_rows': len(sorted_rows),
                    'first_timestamp': str(sorted_rows[0]['timestamp']) if sorted_rows else None,
                    'last_timestamp': str(sorted_rows[-1]['timestamp']) if sorted_rows else None
                }
            )
            
            rows_with_full_indicators = 0
            rows_with_partial_indicators = 0
            
            for i, row in enumerate(sorted_rows):
                try:
                    # Calculs des indicateurs
                    rsi_14 = self._calculate_rsi(sorted_rows, i, period=14)
                    sma_20 = self._calculate_sma(sorted_rows, i, period=20)
                    ema_50 = self._calculate_ema(sorted_rows, i, period=50)
                    ema_12 = self._calculate_ema(sorted_rows, i, period=12)
                    ema_26 = self._calculate_ema(sorted_rows, i, period=26)
                    macd = ema_12 - ema_26 if ema_12 and ema_26 else None
                    macd_signal = self._calculate_macd_signal(sorted_rows, i)
                    bb_middle, bb_upper, bb_lower = self._calculate_bollinger_bands(sorted_rows, i, period=20)
                    
                    if all([sma_20, ema_50, rsi_14, macd, macd_signal, bb_middle]):
                        rows_with_full_indicators += 1
                    else:
                        rows_with_partial_indicators += 1
                    
                    enriched_row = {
                        **row,
                        'sma_20': sma_20,
                        'ema_50': ema_50,
                        'rsi_14': rsi_14,
                        'macd': macd,
                        'macd_signal': macd_signal,
                        'bb_upper': bb_upper,
                        'bb_middle': bb_middle,
                        'bb_lower': bb_lower,
                        'source': 'streaming',
                        'ingestion_timestamp': datetime.now()
                    }
                    
                    yield enriched_row
                    
                except Exception as e:
                    self.errors_count += 1
                    logger.error(
                        "Erreur lors du calcul des indicateurs pour une ligne",
                        extra={
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'symbol': symbol,
                            'row_index': i,
                            'timestamp': str(row.get('timestamp')),
                            'total_errors': self.errors_count
                        }
                    )
            
            # Log de résumé
            logger.info(
                f"Calcul terminé pour {symbol}",
                extra={
                    'symbol': symbol,
                    'total_rows_processed': len(sorted_rows),
                    'rows_with_full_indicators': rows_with_full_indicators,
                    'rows_with_partial_indicators': rows_with_partial_indicators,
                    'full_indicators_rate': f"{(rows_with_full_indicators / len(sorted_rows) * 100):.2f}%" if sorted_rows else "0%"
                }
            )
            
        except Exception as e:
            self.errors_count += 1
            logger.error(
                "Erreur critique lors du traitement d'un groupe",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'symbol': symbol if 'symbol' in locals() else 'UNKNOWN',
                    'total_errors': self.errors_count
                }
            )
    
    # ... (garde toutes les méthodes _calculate_* inchangées)
    
    def _calculate_rsi(self, rows, current_idx, period=14):
        """Calcul du RSI"""
        if current_idx < period:
            return None
        
        try:
            prices = [rows[i]['close'] for i in range(current_idx - period, current_idx + 1)]
            gains = []
            losses = []
            
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception as e:
            logger.error(
                "Erreur calcul RSI",
                extra={'error': str(e), 'current_idx': current_idx, 'period': period}
            )
            return None
    
    def _calculate_sma(self, rows, current_idx, period=20):
        """Calcul du SMA"""
        if current_idx < period - 1:
            return None
        
        try:
            prices = [rows[i]['close'] for i in range(current_idx - period + 1, current_idx + 1)]
            return round(sum(prices) / len(prices), 2)
        except Exception as e:
            logger.error("Erreur calcul SMA", extra={'error': str(e)})
            return None
    
    def _calculate_ema(self, rows, current_idx, period=50):
        """Calcul de l'EMA (simplifié comme SMA)"""
        if current_idx < period - 1:
            return None
        
        try:
            prices = [rows[i]['close'] for i in range(current_idx - period + 1, current_idx + 1)]
            return round(sum(prices) / len(prices), 2)
        except Exception as e:
            logger.error("Erreur calcul EMA", extra={'error': str(e)})
            return None
    
    def _calculate_macd_signal(self, rows, current_idx):
        """Calcul du signal MACD"""
        if current_idx < 35:
            return None
        
        try:
            macd_values = []
            for i in range(current_idx - 8, current_idx + 1):
                ema_12 = self._calculate_ema(rows, i, period=12)
                ema_26 = self._calculate_ema(rows, i, period=26)
                if ema_12 and ema_26:
                    macd_values.append(ema_12 - ema_26)
            
            if len(macd_values) < 9:
                return None
            
            return round(sum(macd_values) / len(macd_values), 2)
        except Exception as e:
            logger.error("Erreur calcul MACD Signal", extra={'error': str(e)})
            return None
    
    def _calculate_bollinger_bands(self, rows, current_idx, period=20):
        """Calcul des Bollinger Bands"""
        if current_idx < period - 1:
            return None, None, None
        
        try:
            prices = [rows[i]['close'] for i in range(current_idx - period + 1, current_idx + 1)]
            bb_middle = sum(prices) / len(prices)
            variance = sum((p - bb_middle) ** 2 for p in prices) / len(prices)
            std_dev = variance ** 0.5
            bb_upper = bb_middle + (2 * std_dev)
            bb_lower = bb_middle - (2 * std_dev)
            
            return round(bb_middle, 2), round(bb_upper, 2), round(bb_lower, 2)
        except Exception as e:
            logger.error("Erreur calcul Bollinger Bands", extra={'error': str(e)})
            return None, None, None