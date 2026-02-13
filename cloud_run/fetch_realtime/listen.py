import os
import time
while True:
    os.system("gcloud pubsub subscriptions pull crypto-klines-monitoring-sub --limit=5 --auto-ack")
    time.sleep(5)
