import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io import ReadFromPubSub, WriteToText
from apache_beam import window
import logging
import json
import os

from CalculateIndicators import CalculateIndicators
from CleanData import CleanData
from ParsePubSubMessage import ParsePubSubMessage


# Configuration
PROJET_ID = "training-gcp-484513"
SUBSCRIPTION = "crypto-klines-monitoring-sub"

current_dir = os.path.dirname(os.path.abspath(__file__))
credentials_path = os.path.join(current_dir, '..', 'infrastructure', 'configs', 'credential.json')
credentials_path = os.path.abspath(credentials_path)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path


# Logger pour le main
logger = logging.getLogger(__name__)


def format_for_bigquery(element):
    """
    Formater les données pour BigQuery.
    Convertir les types Python en types compatibles BigQuery.
    """
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
    # Log de démarrage
    logger.info(
        "Pipeline Dataflow démarré",
        extra={
            'project_id': PROJET_ID,
            'subscription': SUBSCRIPTION,
            'runner': 'DirectRunner'
        }
    )
    
    # Configuration
    options = PipelineOptions([
        '--runner=DirectRunner',
        '--streaming',
        '--temp_location=./temp',
        f'--project={PROJET_ID}',
    ])
    
    options.view_as(StandardOptions).streaming = True
    
    try:
        with beam.Pipeline(options=options) as pipeline:
            
            # Étape 1 : Lire et parser
            messages = (
                pipeline
                | 'Lire Pub/Sub' >> ReadFromPubSub(
                    subscription=f'projects/{PROJET_ID}/subscriptions/{SUBSCRIPTION}'
                )
                | 'Parser JSON' >> beam.ParDo(ParsePubSubMessage())
            )
            
            # Étape 2 : Nettoyer
            cleaned_data = (
                messages
                | 'Nettoyer' >> beam.ParDo(CleanData())
            )
            
            # Étape 3 : Grouper
            grouped_by_symbol = (
                cleaned_data
                | 'Ajouter clé symbol' >> beam.Map(lambda x: (x['symbol'], x))
                | 'Fenêtre 5 min' >> beam.WindowInto(window.FixedWindows(300))
                | 'Grouper par symbol' >> beam.GroupByKey()
            )
            
            # Étape 4 : Calculer indicateurs
            with_indicators = (
                grouped_by_symbol
                | 'Calculer indicateurs' >> beam.ParDo(CalculateIndicators())
            )
            
            # Étape 5 : Écrire
            output = (
                with_indicators
                | 'Convertir en JSON' >> beam.Map(lambda x: json.dumps(x, default=str))
                | 'Écrire résultat' >> beam.io.WriteToText(
                    'output_enriched',
                    file_name_suffix='.jsonl'
                )
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