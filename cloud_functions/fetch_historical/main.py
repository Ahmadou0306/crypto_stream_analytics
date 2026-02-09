import functions_framework
import requests
from datetime import datetime, timedelta
from google.cloud import storage
import time





# https://crypto-stream-analytics-fetch-historical-data-1084139302044.europe-west1.run.app

def fetch_all_klines(symbol, interval, start_ts, end_ts):
    all_data = []
    current_start = start_ts
    limit = 1000
    
    while current_start < end_ts:
        url = (
            "https://api.binance.com/api/v3/klines?"
            f"symbol={symbol}&"
            f"interval={interval}&"
            f"startTime={current_start}&"
            f"endTime={end_ts}&"
            f"limit={limit}"
        )
        
        # Gestion des erreurs avec retry
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if not data:  # Plus de données
                        return all_data
                    
                    all_data.extend(data)
                    
                    # Mettre à jour pour la prochaine requête
                    current_start = data[-1][6] + 1  # Close time + 1ms
                    break
                    
                elif response.status_code == 429:
                    time.sleep(60)
                    continue
                    
                else:
                    time.sleep(2)
                    continue
                    
            except requests.exceptions.Timeout:
                time.sleep(2)
                continue
                
            except requests.exceptions.ConnectionError:
                time.sleep(5)
                continue
                
            except Exception as e:
                return all_data
        
        # Délai entre requêtes
        time.sleep(0.5)
    
    return all_data



import pandas as pd

def convert_to_dataframe(data, symbol):   
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    
    # Convertir les types
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['trades'] = df['trades'].astype(int)
    
    # Ajouter colonne symbol
    df['symbol'] = symbol
    
    # Supprimer colonnes inutiles
    df = df.drop(['ignore', 'close_time'], axis=1)
    
    # Réorganiser colonnes
    df = df[['symbol', 'open_time', 'open', 'high', 'low', 'close', 
             'volume', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote']]
    
    return df

from google.cloud import storage
import io

def upload_dataframe_to_gcs(df, bucket_name, destination_path):
    # Initialiser le client
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    
    # Convertir DataFrame en CSV en mémoire
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    
    # Upload le contenu du buffer
    print(f"Upload vers gs://{bucket_name}/{destination_path}...")
    blob.upload_from_string(csv_buffer.getvalue(), content_type='text/csv')
    
    print(f"DataFrame uploadé avec succès!")
    return f"gs://{bucket_name}/{destination_path}"



@functions_framework.http
def fetch_historical_data():
    symbols = ["BTCUSDT", "ETHUSDT"]
    interval = "15m"
    bucket_name = "crypto-stream-analytics-data-dev"
    
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5) # 5ans 
    
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    
    for symbol in symbols:

        data = fetch_all_klines(symbol, interval, start_ts, end_ts)
        filename = f"{symbol.lower()}-{start_date.strftime("YYYYMMDD")}-{end_date.strftime("YYYYMMDD")}"
        print(f"{symbol}: {len(data)} candles au total\n")
        df = convert_to_dataframe(data, symbol)
        destination = f"{symbol.lower()}/{filename}"
        gcs_path = upload_dataframe_to_gcs(df, bucket_name, destination)

        gcs_path