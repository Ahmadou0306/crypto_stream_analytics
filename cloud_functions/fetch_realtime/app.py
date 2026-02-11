from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "crypto-stream-placeholder"}), 200

@app.route('/')
def root():
    return jsonify({
        "message": "Crypto Stream Ingestion Service",
        "status": "placeholder",
        "environment": os.getenv('ENVIRONMENT', 'unknown')
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
