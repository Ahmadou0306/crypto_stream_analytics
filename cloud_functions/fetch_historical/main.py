import functions_framework
import requests
from datetime import datetime, timedelta
from google.cloud import storage
import time
import io
import json
import logging

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upload_logs_to_gcs(logs_data, bucket_name, log_type="execution"):
    """Upload les logs vers GCS"""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Chemin du fichier de log
        now = datetime.now()
        log_path = f"historical_fetch/{now.strftime('%Y/%m/%d')}/{log_type}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        
        blob = bucket.blob(log_path)
        blob.upload_from_string(
            json.dumps(logs_data, indent=2, default=str),
            content_type='application/json'
        )
        
        logger.info(f"Logs uploadés: gs://{bucket_name}/{log_path}")
        return f"gs://{bucket_name}/{log_path}"
    except Exception as e:
        logger.error(f"Erreur upload logs: {e}")
        return None


def fetch_all_klines(symbol, interval, start_ts, end_ts, logs_list):
    """Récupère les données Binance avec logging"""
    all_data = []
    current_start = start_ts
    limit = 1000
    api_calls = 0
    errors = []
    
    while current_start < end_ts:
        url = (
            "https://api.binance.com/api/v3/klines?"
            f"symbol={symbol}&"
            f"interval={interval}&"
            f"startTime={current_start}&"
            f"endTime={end_ts}&"
            f"limit={limit}"
        )
        
        api_calls += 1
        
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if not data:
                        logger.info(f"{symbol}: Fin des données")
                        return all_data, api_calls, errors
                    
                    all_data.extend(data)
                    current_start = data[-1][6] + 1
                    break
                    
                elif response.status_code == 429:
                    error_msg = f"{symbol}: Rate limit atteint (tentative {attempt+1}/3)"
                    logger.warning(error_msg)
                    errors.append({
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "error": "rate_limit",
                        "attempt": attempt + 1
                    })
                    time.sleep(60)
                    continue
                    
                else:
                    error_msg = f"{symbol}: Erreur HTTP {response.status_code}"
                    logger.warning(error_msg)
                    errors.append({
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "error": f"http_{response.status_code}",
                        "attempt": attempt + 1
                    })
                    time.sleep(2)
                    continue
                    
            except requests.exceptions.Timeout:
                error_msg = f"{symbol}: Timeout (tentative {attempt+1}/3)"
                logger.warning(error_msg)
                errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "error": "timeout",
                    "attempt": attempt + 1
                })
                time.sleep(2)
                continue
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"{symbol}: Erreur connexion (tentative {attempt+1}/3)"
                logger.warning(error_msg)
                errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "error": "connection_error",
                    "detail": str(e),
                    "attempt": attempt + 1
                })
                time.sleep(5)
                continue
                
            except Exception as e:
                error_msg = f"{symbol}: Erreur inattendue: {e}"
                logger.error(error_msg)
                errors.append({
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "error": "unexpected",
                    "detail": str(e)
                })
                return all_data, api_calls, errors
        
        time.sleep(0.5)
    
    return all_data, api_calls, errors


import pandas as pd

def convert_to_dataframe(data, symbol):   
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['trades'] = df['trades'].astype(int)
    
    df['symbol'] = symbol
    df = df.drop(['ignore', 'close_time'], axis=1)
    
    df = df[['symbol', 'open_time', 'open', 'high', 'low', 'close', 
             'volume', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote']]
    
    return df


def upload_dataframe_to_gcs(df, bucket_name, destination_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    
    logger.info(f"Upload vers gs://{bucket_name}/{destination_path}...")
    blob.upload_from_string(
        csv_buffer.getvalue(), 
        content_type='text/csv',
        timeout=300 
    )    
    logger.info(f"Upload réussi: {len(df)} lignes")
    return f"gs://{bucket_name}/{destination_path}"


@functions_framework.http
def fetch_historical_data(request):
    """Point d'entrée de la Cloud Function avec logging complet"""
    
    start_time = datetime.now()
    symbols = ["BTCUSDT", "ETHUSDT"]
    interval = "15m"
    data_bucket = "crypto-stream-analytics-data-dev"
    logs_bucket = "crypto-stream-analytics-logs-dev"
    
    uploaded_files = []
    execution_logs = {
        "execution_id": start_time.strftime('%Y%m%d_%H%M%S'),
        "start_time": start_time.isoformat(),
        "function": "fetch_historical_data",
        "symbols": symbols,
        "interval": interval,
        "years": [],
        "summary": {}
    }
    
    all_errors = []
    
    try:
        # Boucle sur 5 années
        for year_offset in range(5):
            end_date = datetime.now() - timedelta(days=365 * year_offset)
            start_date = end_date - timedelta(days=365)
            
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            
            year_log = {
                "year": start_date.year,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols_processed": []
            }
            
            for symbol in symbols:
                symbol_start = datetime.now()
                logger.info(f"Traitement {symbol} - Année {start_date.year}...")
                
                # Récupération des données
                data, api_calls, errors = fetch_all_klines(
                    symbol, interval, start_ts, end_ts, all_errors
                )
                all_errors.extend(errors)
                
                logger.info(f"{symbol}: {len(data)} candles récupérées")
                
                # Conversion en DataFrame
                df = convert_to_dataframe(data, symbol)
                
                # Stats sur les données
                stats = {
                    "open_price_min": float(df['open'].min()),
                    "open_price_max": float(df['open'].max()),
                    "volume_total": float(df['volume'].sum()),
                    "trades_total": int(df['trades'].sum())
                }
                
                # Upload
                filename = f"{symbol.lower()}-{start_date.year}.csv"
                destination = f"historical/{symbol.lower()}/{filename}"
                
                gcs_path = upload_dataframe_to_gcs(df, data_bucket, destination)
                uploaded_files.append(gcs_path)
                
                symbol_elapsed = (datetime.now() - symbol_start).total_seconds()
                
                # Log pour ce symbol
                symbol_log = {
                    "symbol": symbol,
                    "candles_fetched": len(data),
                    "api_calls": api_calls,
                    "errors_count": len(errors),
                    "execution_time_seconds": symbol_elapsed,
                    "gcs_path": gcs_path,
                    "stats": stats,
                    "status": "success"
                }
                
                year_log["symbols_processed"].append(symbol_log)
                logger.info(f"{symbol} terminé en {symbol_elapsed:.2f}s")
            
            execution_logs["years"].append(year_log)
        
        # Fin de l'exécution
        end_time = datetime.now()
        total_elapsed = (end_time - start_time).total_seconds()
        
        execution_logs["end_time"] = end_time.isoformat()
        execution_logs["total_execution_time_seconds"] = total_elapsed
        execution_logs["total_files_uploaded"] = len(uploaded_files)
        execution_logs["total_errors"] = len(all_errors)
        execution_logs["status"] = "success"
        
        # Résumé
        total_candles = sum(
            symbol_log["candles_fetched"] 
            for year in execution_logs["years"] 
            for symbol_log in year["symbols_processed"]
        )
        
        execution_logs["summary"] = {
            "total_candles": total_candles,
            "total_years": len(execution_logs["years"]),
            "total_symbols": len(symbols),
            "avg_time_per_year": total_elapsed / len(execution_logs["years"])
        }
        
        logger.info(f"Exécution terminée: {total_candles} candles en {total_elapsed:.2f}s")
        
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        execution_logs["status"] = "failed"
        execution_logs["error"] = str(e)
        execution_logs["end_time"] = datetime.now().isoformat()
    
    # Upload des logs d'exécution
    upload_logs_to_gcs(execution_logs, logs_bucket, "execution")
    
    # Upload des erreurs si présentes
    if all_errors:
        upload_logs_to_gcs({
            "execution_id": execution_logs["execution_id"],
            "errors": all_errors
        }, logs_bucket, "errors")
    
    return {
        "status": execution_logs["status"],
        "execution_id": execution_logs["execution_id"],
        "files": uploaded_files,
        "total_candles": execution_logs.get("summary", {}).get("total_candles", 0),
        "execution_time": execution_logs.get("total_execution_time_seconds", 0),
        "logs_uploaded": True
    }, 200