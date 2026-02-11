from flask import Flask, jsonify
import os
import signal
import sys
from websocket_client import BinanceWebSocketClient
from logger_gcs import GCSLogger
from publisher import PubSubPublisher

# Configuration depuis variables d'environnement
PROJECT_ID = os.getenv('PROJECT_ID')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
GCS_BUCKET_LOGS = os.getenv('GCS_BUCKET_LOGS', f'crypto-stream-analytics-logs-{ENVIRONMENT}')
BINANCE_INTERVAL = os.getenv('BINANCE_STREAM_TYPE', 'kline_5m').replace('kline_', '')
PUBSUB_TOPIC = os.getenv('PUBSUB_TOPIC', 'crypto-klines-raw')
SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT"]

# Initialiser Flask
app = Flask(__name__)

# Initialiser GCS Logger
gcs_logger = GCSLogger(bucket_name=GCS_BUCKET_LOGS, project_id=PROJECT_ID)


pubsub_publisher = PubSubPublisher(
    project_id=PROJECT_ID,
    topic_name=PUBSUB_TOPIC
)


# Initialiser WebSocket Client
ws_client = BinanceWebSocketClient(
    symbols=SYMBOLS,
    interval=BINANCE_INTERVAL,
    gcs_logger=gcs_logger,
    pubsub_publisher=pubsub_publisher
)

# Démarrer le WebSocket au démarrage de l'app
ws_client.start()

@app.route('/health')
def health():
    """Health check endpoint"""
    stats = ws_client.get_stats()
    
    return jsonify({
        "status": "ok",
        "service": "crypto-stream-realtime",
        "environment": ENVIRONMENT,
        "websocket_running": ws_client.running,
        "stats": stats,
        "pubsub_stats": pubsub_publisher.get_stats()
    }), 200


@app.route('/')
def root():
    return jsonify({
        "message": "Crypto Stream Ingestion Service - Real-time",
        "status": "running",
        "environment": ENVIRONMENT,
        "symbols": SYMBOLS,
        "interval": BINANCE_INTERVAL,
        "gcs_bucket": GCS_BUCKET_LOGS,
        "pubsub_topic": PUBSUB_TOPIC
    }), 200


@app.route('/stats')
def stats():
    return jsonify({
        "websocket": ws_client.get_stats(),
        "pubsub": pubsub_publisher.get_stats()
    }), 200


def shutdown_handler(signum, frame):
    ws_client.stop()
    sys.exit(0)


# Enregistrer les handlers de signal
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)