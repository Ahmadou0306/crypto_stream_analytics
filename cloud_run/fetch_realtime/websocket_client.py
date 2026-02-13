"""
Client WebSocket pour Binance Stream API
"""
import json
import time
import threading
import logging
from datetime import datetime
from typing import List
import websocket
from publisher import PubSubPublisher


# Logger
logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """Client WebSocket pour écouter les candles Binance en temps réel"""
    
    BASE_URL = "wss://stream.binance.com:9443/ws"
    
    def __init__(self, symbols: List[str], interval: str, pubsub_publisher: PubSubPublisher):
        self.symbols = [s.lower() for s in symbols]
        self.interval = interval
        self.pubsub_publisher = pubsub_publisher
        
        # Construire l'URL du stream
        # Format: btcusdt@kline_5m/ethusdt@kline_5m/...
        streams = '/'.join([f"{symbol}@kline_{interval}" for symbol in self.symbols])
        self.url = f"{self.BASE_URL}/{streams}"
        
        self.ws = None
        self.running = False
        self.thread = None
        
        # Statistiques
        self.stats = {
            "start_time": None,
            "messages_received": 0,
            "klines_processed": 0,
            "errors": 0,
            "last_message_time": None
        }
        
        logger.info(
            "WebSocket client initialisé",
            extra={
                'url': self.url,
                'symbols': self.symbols,
                'interval': interval
            }
        )
    
    def on_message(self, ws, message):
        """Callback appelé à chaque message reçu"""
        try:
            data = json.loads(message)
            
            # Mise à jour stats
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = datetime.now().isoformat()
            
            # Extraire les données de la candle
            if 'k' in data:  # Message de type kline
                kline = data['k']
                
                # On ne traite que les candles fermées
                if kline['x']:  # x = True signifie candle fermée
                    kline_data = {
                        "event_time": datetime.fromtimestamp(data['E'] / 1000).isoformat(),
                        "symbol": kline['s'],
                        "interval": kline['i'],
                        "start_time": datetime.fromtimestamp(kline['t'] / 1000).isoformat(),
                        "close_time": datetime.fromtimestamp(kline['T'] / 1000).isoformat(),
                        "open": float(kline['o']),
                        "high": float(kline['h']),
                        "low": float(kline['l']),
                        "close": float(kline['c']),
                        "volume": float(kline['v']),
                        "quote_volume": float(kline['q']),
                        "trades": int(kline['n']),
                        "taker_buy_base": float(kline['V']),
                        "taker_buy_quote": float(kline['Q'])
                    }
                    
                    # Publier dans Pub/Sub
                    if self.pubsub_publisher:
                        self.pubsub_publisher.publish_kline(kline_data)
                    
                    self.stats["klines_processed"] += 1
                    
                    # Log de la candle fermée
                    logger.info(
                        "Candle fermée reçue",
                        extra={
                            'symbol': kline_data['symbol'],
                            'interval': kline_data['interval'],
                            'close': kline_data['close'],
                            'volume': kline_data['volume'],
                            'start_time': kline_data['start_time'],
                            'total_klines_processed': self.stats["klines_processed"]
                        }
                    )
            
        except json.JSONDecodeError as e:
            self.stats["errors"] += 1
            logger.error(
                "Erreur de parsing JSON du message WebSocket",
                extra={
                    'error': str(e),
                    'message_preview': message[:500],
                    'total_errors': self.stats["errors"]
                }
            )
        
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(
                "Erreur lors du traitement du message WebSocket",
                extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'message_preview': message[:500],
                    'total_errors': self.stats["errors"]
                }
            )
    
    def on_error(self, ws, error):
        """Callback appelé en cas d'erreur WebSocket"""
        self.stats["errors"] += 1
        logger.error(
            "Erreur WebSocket",
            extra={
                'error': str(error),
                'error_type': type(error).__name__,
                'total_errors': self.stats["errors"],
                'url': self.url
            }
        )
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback appelé à la fermeture de la connexion"""
        logger.warning(
            "WebSocket fermé",
            extra={
                'close_code': close_status_code,
                'close_message': close_msg,
                'url': self.url,
                'stats': self.stats
            }
        )
    
    def on_open(self, ws):
        """Callback appelé à l'ouverture de la connexion"""
        self.stats["start_time"] = datetime.now().isoformat()
        
        logger.info(
            "WebSocket connecté avec succès",
            extra={
                'url': self.url,
                'symbols': self.symbols,
                'interval': self.interval,
                'start_time': self.stats["start_time"]
            }
        )
    
    def start(self):
        """Démarrer le client WebSocket"""
        if self.running:
            logger.warning("WebSocket déjà en cours d'exécution")
            return
        
        self.running = True
        
        # Créer l'instance WebSocket
        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Lancer dans un thread
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()
        
        logger.info(
            "WebSocket démarré en background",
            extra={
                'thread_name': self.thread.name,
                'daemon': True
            }
        )
    
    def _run_forever(self):
        """Boucle principale du WebSocket avec reconnexion automatique"""
        while self.running:
            try:
                logger.info("Démarrage de la connexion WebSocket")
                self.ws.run_forever()
                
                # Si on sort de run_forever et qu'on doit continuer, attendre avant reconnexion
                if self.running:
                    logger.warning(
                        "Connexion WebSocket interrompue - Reconnexion dans 5s",
                        extra={'wait_seconds': 5}
                    )
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(
                    "Erreur dans la boucle WebSocket",
                    extra={
                        'error': str(e),
                        'error_type': type(e).__name__
                    }
                )
                
                if self.running:
                    logger.info("Tentative de reconnexion dans 5s")
                    time.sleep(5)
    
    def stop(self):
        """Arrêter le client WebSocket"""
        logger.info(
            "Arrêt du WebSocket demandé",
            extra={'stats': self.stats}
        )
        
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        logger.info(
            "WebSocket arrêté - Statistiques finales",
            extra={
                'duration': f"{datetime.now().isoformat()} - {self.stats['start_time']}",
                'total_messages': self.stats["messages_received"],
                'total_klines': self.stats["klines_processed"],
                'total_errors': self.stats["errors"],
                'last_message': self.stats["last_message_time"]
            }
        )
    
    def get_stats(self) -> dict:
        """Récupérer les statistiques actuelles"""
        return self.stats.copy()