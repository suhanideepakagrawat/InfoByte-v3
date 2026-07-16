import os
from pathlib import Path
from transformers import pipeline
from app.db.query_logger import log_all_query  # Import the logger

class IntentClassifier:
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        # Point to the newly trained model folder
        self.model_path = project_root / "nlp" / "optimized_intent_model"
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model weights not found at: {self.model_path}")

        print(f"[INIT] Loading RoBERTa Classifier from: {self.model_path}")
        
        self.classifier = pipeline(
            "text-classification", 
            model=str(self.model_path), 
            tokenizer=str(self.model_path), 
            top_k=None
        )

    def predict_intents(self, query: str):
        if not query.strip():
            return []
        
        results = self.classifier(query)[0]
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        top_result = results[0]
        
        # Log every interaction
        log_all_query(query, top_result['label'], top_result['score'])
            
        return results

intent_classifier = IntentClassifier()