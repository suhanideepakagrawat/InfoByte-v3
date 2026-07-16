import numpy as np
import onnxruntime as ort
from pathlib import Path
from transformers import AutoTokenizer, AutoConfig
from app.db.query_logger import log_all_query  # Import the logger

class IntentClassifier:
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.model_path = project_root / "nlp" / "exports" / "quantized_model"

        if not self.model_path.exists():
            raise FileNotFoundError(f"Quantized model not found at: {self.model_path}")

        print(f"[INIT] Loading ONNX Intent Classifier from: {self.model_path}")

        onnx_file = self.model_path / "model_quantized.onnx"
        if not onnx_file.exists():
            candidates = list(self.model_path.glob("*.onnx"))
            if not candidates:
                raise FileNotFoundError(f"No .onnx file found in {self.model_path}")
            onnx_file = candidates[0]

        self.session = ort.InferenceSession(str(onnx_file), providers=["CPUExecutionProvider"])
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
        self.config = AutoConfig.from_pretrained(str(self.model_path))
        self.id2label = self.config.id2label

        self._input_names = {i.name for i in self.session.get_inputs()}

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        exp = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        return exp / exp.sum(axis=-1, keepdims=True)

    def predict_intents(self, query: str):
        if not query.strip():
            return []

        inputs = self.tokenizer(query, return_tensors="np", truncation=True, padding=True)
        onnx_inputs = {k: v for k, v in inputs.items() if k in self._input_names}

        logits = self.session.run(None, onnx_inputs)[0]
        probs = self._softmax(logits)[0]

        results = [
            {"label": self.id2label[i], "score": float(probs[i])}
            for i in range(len(probs))
        ]
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        top_result = results[0]

        # Log every interaction
        log_all_query(query, top_result["label"], top_result["score"])

        return results

intent_classifier = IntentClassifier()