import apache_beam as beam
import json
import logging

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