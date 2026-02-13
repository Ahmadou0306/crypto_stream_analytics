from datetime import datetime
import apache_beam as beam
import logging

logger = logging.getLogger(__name__)


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