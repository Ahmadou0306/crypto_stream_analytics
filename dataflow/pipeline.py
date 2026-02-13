import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, GoogleCloudOptions, WorkerOptions
from apache_beam.io import ReadFromPubSub, WriteToBigQuery
from apache_beam import window
import logging
import argparse

from CalculateIndicators import CalculateIndicators
from CleanData import CleanData
from ParsePubSubMessage import ParsePubSubMessage
import os

logger = logging.getLogger(__name__)


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