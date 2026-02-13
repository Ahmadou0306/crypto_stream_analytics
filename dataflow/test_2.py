import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io import ReadFromPubSub, WriteToBigQuery
from apache_beam import window
import logging
import os

from CalculateIndicators import CalculateIndicators
from CleanData import CleanData
from ParsePubSubMessage import ParsePubSubMessage


# configurer dans l'env
PROJET_ID = "training-gcp-484513"
SUBSCRIPTION = "crypto-klines-monitoring-sub"
DATASET_ID = "crypto_analytics"
TABLE_ID = "market_data_unified"

current_dir = os.path.dirname(os.path.abspath(__file__))
credentials_path = os.path.join(current_dir, '..', 'infrastructure', 'configs', 'credential.json')
credentials_path = os.path.abspath(credentials_path)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

# Logger
logger = logging.getLogger(__name__)

#Format de bq
def format_for_bigquery(element):
    try:
        # Convertir date et timestamp en strings ISO
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
        logger.error(
            "Erreur lors du formatage pour BigQuery",
            extra={
                'error': str(e),
                'element': str(element)[:200]
            }
        )
        return None


def run_pipeline():
    logger.info(
        "Pipeline Dataflow démarré",
        extra={
            'project_id': PROJET_ID,
            'subscription': SUBSCRIPTION,
            'dataset': DATASET_ID,
            'table': TABLE_ID,
            'runner': 'DirectRunner'
        }
    )
    
    # Configuration du pipeline
    options = PipelineOptions([
        '--runner=DirectRunner',
        '--streaming',
        '--temp_location=./temp',
        f'--project={PROJET_ID}',
    ])
    
    options.view_as(StandardOptions).streaming = True
    
    # Schéma BigQuery (doit correspondre à ta table)
    table_schema = {
        'fields': [
            # Dimensions temporelles
            {'name': 'timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
            {'name': 'date', 'type': 'DATE', 'mode': 'REQUIRED'},
            {'name': 'hour', 'type': 'INTEGER', 'mode': 'REQUIRED'},
            {'name': 'day_of_week', 'type': 'STRING', 'mode': 'NULLABLE'},
            
            # Dimensions crypto
            {'name': 'symbol', 'type': 'STRING', 'mode': 'REQUIRED'},
            
            # OHLCV
            {'name': 'open', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'high', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'low', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'close', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'volume', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'trades', 'type': 'INTEGER', 'mode': 'NULLABLE'},
            
            # Indicateurs techniques
            {'name': 'sma_20', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'ema_50', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'rsi_14', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'macd', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'macd_signal', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_upper', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_middle', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            {'name': 'bb_lower', 'type': 'FLOAT', 'mode': 'NULLABLE'},
            
            # Métadonnées
            {'name': 'source', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'ingestion_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'}
        ]
    }
    
    try:
        with beam.Pipeline(options=options) as pipeline:
            
            # Lire et parser
            messages = (
                pipeline
                | 'Lire Pub/Sub' >> ReadFromPubSub(
                    subscription=f'projects/{PROJET_ID}/subscriptions/{SUBSCRIPTION}'
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
            
            # Formater pour BigQuery
            formatted_data = (
                with_indicators
                | 'Formater pour BigQuery' >> beam.Map(format_for_bigquery)
                | 'Filtrer None' >> beam.Filter(lambda x: x is not None)
            )
            
            # Écrire dans BigQuery
            formatted_data | 'Écrire dans BigQuery' >> WriteToBigQuery(
                table=f'{PROJET_ID}:{DATASET_ID}.{TABLE_ID}',
                schema=table_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
                method='STREAMING_INSERTS'  # Pour streaming en temps réel
            )
        
        logger.info(
            "Pipeline terminé avec succès",
            extra={'project_id': PROJET_ID, 'status': 'SUCCESS'}
        )
        
    except Exception as e:
        logger.error(
            "Erreur critique dans le pipeline",
            extra={
                'error': str(e),
                'error_type': type(e).__name__,
                'project_id': PROJET_ID
            }
        )
        raise


if __name__ == '__main__':
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_pipeline()