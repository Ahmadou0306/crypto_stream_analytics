import logging
from datetime import datetime
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, GoogleCloudOptions, WorkerOptions
from apache_beam.io import ReadFromPubSub, WriteToBigQuery
from apache_beam import window
import argparse
import json
import os

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
        



class CleanData(beam.DoFn):
    
    def __init__(self):
        self.rejected_count = 0
        self.cleaned_count = 0
    
    def process(self, row):
        try:
            # Vérifier que les champs essentiels existent et sont valides
            if not (row.get('open') and row.get('close') and row.get('volume') and float(row.get('volume', 0)) > 0):
                self.rejected_count += 1
                logger.warning(
                    "Données rejetées - champs manquants ou volume invalide",
                    extra={
                        'symbol': row.get('symbol'),
                        'timestamp': row.get('start_time', row.get('event_time')),
                        'volume': row.get('volume'),
                        'total_rejected': self.rejected_count
                    }
                )
                return
            
            # Parser le timestamp
            timestamp_str = row.get('start_time', row.get('event_time'))
            
            if 'T' in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            # Créer les données nettoyées
            cleaned = {
                'timestamp': timestamp,
                'date': timestamp.date(),
                'hour': timestamp.hour,
                'day_of_week': timestamp.strftime('%A'),
                'symbol': row.get('symbol'),
                'open': float(row.get('open')),
                'high': float(row.get('high')),
                'low': float(row.get('low')),
                'close': float(row.get('close')),
                'volume': float(row.get('volume')),
                'trades': int(row.get('trades', 0))
            }
            
            self.cleaned_count += 1
            
            # Log tous les 100 enregistrements pour éviter le spam
            if self.cleaned_count % 100 == 0:
                logger.info(
                    f"{self.cleaned_count} enregistrements nettoyés",
                    extra={
                        'total_cleaned': self.cleaned_count,
                        'total_rejected': self.rejected_count
                    }
                )
            
            yield cleaned
                
        except ValueError as e:
            self.rejected_count += 1
            logger.error(
                "Erreur de conversion de type lors du nettoyage",
                extra={
                    'error': str(e),
                    'error_type': 'ValueError',
                    'symbol': row.get('symbol'),
                    'timestamp': row.get('start_time', row.get('event_time')),
                    'total_rejected': self.rejected_count
                }
            )
            
        except Exception as e:
            self.rejected_count += 1
            logger.error(
                "Erreur inattendue lors du nettoyage",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'symbol': row.get('symbol'),
                    'timestamp': row.get('start_time', row.get('event_time')),
                    'total_rejected': self.rejected_count
                }
            )

# Logger structuré pour Cloud Logging
logger = logging.getLogger(__name__)


class ParsePubSubMessage(beam.DoFn):
    
    def __init__(self):
        self.errors = 0
        self.parsed = 0
    
    def process(self, message):
        try:
            # Décoder le message
            data = json.loads(message.decode('utf-8'))
            self.parsed += 1
            
            # Log structuré (automatiquement envoyé à Cloud Logging)
            logger.info(
                "Message Pub/Sub parsé avec succès",
                extra={
                    'symbol': data.get('symbol'),
                    'timestamp': data.get('start_time', data.get('event_time')),
                    'close': data.get('close'),
                    'volume': data.get('volume'),
                    'total_parsed': self.parsed
                }
            )
            
            yield data
            
        except json.JSONDecodeError as e:
            self.errors += 1
            logger.error(
                "Erreur de parsing JSON - format invalide",
                extra={
                    'error': str(e),
                    'message_preview': str(message[:200]),
                    'total_errors': self.errors
                }
            )
            
        except Exception as e:
            self.errors += 1
            logger.error(
                "Erreur inattendue lors du parsing",
                extra={
                    'error_type': type(e).__name__,
                    'error': str(e),
                    'message_preview': str(message[:200]),
                    'total_errors': self.errors
                }
            )






current_dir = os.path.dirname(os.path.abspath(__file__))
credentials_path = os.path.join(current_dir, '..', 'infrastructure', 'configs', 'credential.json')
credentials_path = os.path.abspath(credentials_path)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path



def format_for_bigquery(element):
    """Formater les données pour BigQuery"""
    try:
        formatted = {
            'timestamp': element['timestamp'].isoformat() if hasattr(element['timestamp'], 'isoformat') else str(element['timestamp']),
            'date': element['date'].isoformat() if hasattr(element['date'], 'isoformat') else str(element['date']),
            'hour': int(element['hour']),
            'day_of_week': str(element['day_of_week']),
            'symbol': str(element['symbol']),
            'open': float(element['open']),
            'high': float(element['high']),
            'low': float(element['low']),
            'close': float(element['close']),
            'volume': float(element['volume']),
            'trades': int(element.get('trades', 0)),
            'sma_20': float(element['sma_20']) if element.get('sma_20') is not None else None,
            'ema_50': float(element['ema_50']) if element.get('ema_50') is not None else None,
            'rsi_14': float(element['rsi_14']) if element.get('rsi_14') is not None else None,
            'macd': float(element['macd']) if element.get('macd') is not None else None,
            'macd_signal': float(element['macd_signal']) if element.get('macd_signal') is not None else None,
            'bb_upper': float(element['bb_upper']) if element.get('bb_upper') is not None else None,
            'bb_middle': float(element['bb_middle']) if element.get('bb_middle') is not None else None,
            'bb_lower': float(element['bb_lower']) if element.get('bb_lower') is not None else None,
            'source': str(element['source']),
            'ingestion_timestamp': element['ingestion_timestamp'].isoformat() if hasattr(element['ingestion_timestamp'], 'isoformat') else str(element['ingestion_timestamp'])
        }
        return formatted
    except Exception as e:
        logger.error(f"Erreur formatage BigQuery: {e}")
        return None


def run_pipeline(argv=None):
    """Pipeline principal"""
    
    # Parser les arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, help='GCP Project ID')
    parser.add_argument('--subscription', required=True, help='Pub/Sub subscription')
    parser.add_argument('--dataset', required=True, help='BigQuery dataset')
    parser.add_argument('--table', required=True, help='BigQuery table')
    parser.add_argument('--region', default='europe-west1', help='GCP region')
    parser.add_argument('--temp_location', required=True, help='GCS temp location')
    parser.add_argument('--staging_location', required=True, help='GCS staging location')
    parser.add_argument('--service_account_email', required=False, help='Service account email')
    
    known_args, pipeline_args = parser.parse_known_args(argv)
    
    #Configuration des PipelineOptions avec les valeurs parsées
    pipeline_options = PipelineOptions(pipeline_args)
    
    # Configuration Google Cloud
    google_cloud_options = pipeline_options.view_as(GoogleCloudOptions)
    google_cloud_options.project = known_args.project
    google_cloud_options.region = known_args.region
    google_cloud_options.temp_location = known_args.temp_location
    google_cloud_options.staging_location = known_args.staging_location
    
    if known_args.service_account_email:
        google_cloud_options.service_account_email = known_args.service_account_email
    
    # Configuration standard
    standard_options = pipeline_options.view_as(StandardOptions)
    standard_options.streaming = True
    
    # Configuration des workers (optionnel mais recommandé)
    worker_options = pipeline_options.view_as(WorkerOptions)
    worker_options.machine_type = 'n1-standard-2'  # Type de machine
    worker_options.max_num_workers = 3  # Nombre max de workers
    worker_options.autoscaling_algorithm = 'THROUGHPUT_BASED'
    
    # Schéma BigQuery
    table_schema = {
        'fields': [
            {'name': 'timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
            {'name': 'date', 'type': 'DATE', 'mode': 'REQUIRED'},
            {'name': 'hour', 'type': 'INTEGER', 'mode': 'REQUIRED'},
            {'name': 'day_of_week', 'type': 'STRING', 'mode': 'NULLABLE'},
            {'name': 'symbol', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'open', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'high', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'low', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'close', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'volume', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'trades', 'type': 'INTEGER', 'mode': 'NULLABLE'},
            {'name': 'sma_20', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'ema_50', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'rsi_14', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'macd', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'macd_signal', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_upper', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_middle', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_lower', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'source', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'ingestion_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'}
        ]
    }
    
    logger.info(f"Démarrage du pipeline Dataflow")
    logger.info(f"Project: {known_args.project}")
    logger.info(f"Region: {known_args.region}")
    logger.info(f"Subscription: {known_args.subscription}")
    logger.info(f"BigQuery: {known_args.dataset}.{known_args.table}")
    
    with beam.Pipeline(options=pipeline_options) as pipeline:
        
        # Lire et parser
        messages = (
            pipeline
            | 'Lire Pub/Sub' >> ReadFromPubSub(
                subscription=f'projects/{known_args.project}/subscriptions/{known_args.subscription}'
            )
            | 'Parser JSON' >> beam.ParDo(ParsePubSubMessage())
        )
        
        # Nettoyer
        cleaned_data = (
            messages
            | 'Nettoyer' >> beam.ParDo(CleanData())
        )
        
        # Grouper
        grouped_by_symbol = (
            cleaned_data
            | 'Ajouter clé symbol' >> beam.Map(lambda x: (x['symbol'], x))
            | 'Fenêtre 5 min' >> beam.WindowInto(window.FixedWindows(300))
            | 'Grouper par symbol' >> beam.GroupByKey()
        )
        
        # Calculer indicateurs
        with_indicators = (
            grouped_by_symbol
            | 'Calculer indicateurs' >> beam.ParDo(CalculateIndicators())
        )
        
        # Formater et écrire dans BigQuery
        (
            with_indicators
            | 'Formater pour BigQuery' >> beam.Map(format_for_bigquery)
            | 'Filtrer None' >> beam.Filter(lambda x: x is not None)
            | 'Écrire dans BigQuery' >> WriteToBigQuery(
                table=f'{known_args.project}:{known_args.dataset}.{known_args.table}',
                schema=table_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
                method='STREAMING_INSERTS'
            )
        )
    
    logger.info("Pipeline soumis avec succès à Dataflow")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    run_pipeline()
