import csv
import os
from datetime import datetime

LOG_FILE = "all_queries_log.csv"

def log_all_query(query: str, predicted_intent: str, confidence: float):
    # Ensure directory exists
    if not os.path.exists(os.path.dirname(LOG_FILE)) and os.path.dirname(LOG_FILE):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        
    file_exists = os.path.isfile(LOG_FILE)
    
    # Using 'a' mode (append) is inherently safer for concurrent writes than pandas IO
    with open(LOG_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "query", "predicted_intent", "confidence", "corrected_label"])
        writer.writerow([datetime.now().isoformat(), query, predicted_intent, f"{confidence:.4f}", ""])