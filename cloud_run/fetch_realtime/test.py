import json
import time
import threading
from datetime import datetime
from typing import Callable, List
import websocket
import sys
# client WebSocket pour écouter les candles Binance en temps réel
class BinanceWebSocketClient:
    
    # URL WebSocket Binance
    BASE_URL = "wss://stream.binance.com:9443/ws"
    
    def __init__(self, symbols: List[str], interval: str):
        self.symbols = [s.lower() for s in symbols]
        self.interval = interval
        
        # Construire l'URL du stream format: btcusdt@kline_5m/ethusdt@kline_5m/...
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
        
        print(f"URL: {self.url}")
    
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # Mise à jour stats
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = datetime.now().isoformat()
            
            # Extraire les données de la candle
            if 'k' in data:  # Message de type kline
                kline = data['k']
                
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
                    
                    # Logger dans GCS
                    
                    self.stats["klines_processed"] += 1
                    
                    print(f"Candle fermée: {kline_data['symbol']} | "
                          f"Close: {kline_data['close']} | "
                          f"Volume: {kline_data['volume']:.2f}")
            
        except Exception as e:
            self.stats["errors"] += 1
            error_msg = f"Erreur traitement message: {str(e)}"
            print(f"{error_msg}")
    
    def on_error(self, ws, error):
        self.stats["errors"] += 1
        error_msg = f"WebSocket error: {str(error)}"
        print(f"{error_msg}")
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket fermé - Code: {close_status_code}, Message: {close_msg}")

    
        
        # Logger stats initiales
        self.stats["start_time"] = datetime.now().isoformat()
    
    def start(self):
        if self.running:
            print("WebSocket déjà en cours d'exécution")
            return
        
        self.running = True
        
        # Créer l'instance WebSocket
        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        
        # Lancer dans un thread
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()
        
        print("WebSocket démarré en background")
    
    def _run_forever(self):
        while self.running:
            try:
                self.ws.run_forever()
                
                # Si on sort de run_forever et qu'on doit continuer, attendre avant reconnexion
                if self.running:
                    time.sleep(5)
                    
            except Exception as e:
                error_msg = f"Erreur run_forever: {str(e)}"
                print(f"{error_msg}")
                
                if self.running:
                    time.sleep(5)
    
    def stop(self):
        self.running = False
        
        if self.ws:
            self.ws.close()
        
    
    def get_stats(self) -> dict:
        return self.stats.copy()
    
ENVIRONMENT = "dev"
GCS_BUCKET_LOGS = "crypto-stream-analytics-logs-dev"
BINANCE_INTERVAL = 'kline_5m'.replace('kline_', '')
SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT"]


ws_client = BinanceWebSocketClient(
    symbols=SYMBOLS,
    interval=BINANCE_INTERVAL,
)

ws_client.start()
try:
    # Boucle infinie pour garder le script actif
    while True:
        time.sleep(10)
        stats = ws_client.get_stats()
        print(f"Stats: Messages={stats['messages_received']}, "
              f"Candles={stats['klines_processed']}, "
              f"Erreurs={stats['errors']}")
except KeyboardInterrupt:
    print("\n🛑 Arrêt demandé...")
    ws_client.stop()
    sys.exit(0)

"""
ws_client.stop()
sys.exit(0)
"""