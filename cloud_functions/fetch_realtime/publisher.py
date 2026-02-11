import json
from datetime import datetime
from google.cloud import pubsub_v1
from typing import Dict, Any


class PubSubPublisher:   
    def __init__(self, project_id: str, topic_name: str):
        self.project_id = project_id
        self.topic_name = topic_name
        
        # Créer le client publisher
        self.publisher = pubsub_v1.PublisherClient()
        
        # Créer le topic path complet
        self.topic_path = self.publisher.topic_path(project_id, topic_name)
        
        # Stats
        self.stats = {
            "messages_published": 0,
            "publish_errors": 0,
            "last_publish_time": None
        }
            
    def publish_kline(self, kline_data: Dict[str, Any]) -> None:
        try:
            # Convertir le dict en JSON string
            message_json = json.dumps(kline_data)
            
            # Convertir en bytes (requis par Pub/Sub)
            message_bytes = message_json.encode('utf-8')
            
            # Ajouter des attributs au message
            attributes = {
                'symbol': kline_data.get('symbol', 'UNKNOWN'),
                'interval': kline_data.get('interval', '5m'),
                'source': 'binance-websocket',
                'timestamp': datetime.now().isoformat()
            }
            
            # Publier le message (asynchrone)
            future = self.publisher.publish(
                self.topic_path,
                data=message_bytes,
                **attributes
            )
            
            # Attendre la confirmation
            message_id = future.result(timeout=5.0)
            
            # Mise à jour stats
            self.stats["messages_published"] += 1
            self.stats["last_publish_time"] = datetime.now().isoformat()
                        
        except Exception as e:
            self.stats["publish_errors"] += 1
            error_msg = f"Erreur publication Pub/Sub: {str(e)}"
            raise Exception(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()