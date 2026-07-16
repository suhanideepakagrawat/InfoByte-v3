"""
Exports the trained DistilBERT/RoBERTa intent classifier to ONNX,
then applies dynamic int8 quantization for deployment.
"""
from pathlib import Path
from optimum.onnxruntime import ORTModelForSequenceClassification
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from optimum.onnxruntime import ORTQuantizer
from transformers import AutoTokenizer

SOURCE_MODEL_DIR = "nlp/exports/best_model"      # your trained checkpoint
ONNX_DIR = "nlp/exports/onnx_model"              # intermediate export
QUANTIZED_DIR = "nlp/exports/quantized_model"    # final deployable model

def main():
    Path(ONNX_DIR).mkdir(parents=True, exist_ok=True)
    Path(QUANTIZED_DIR).mkdir(parents=True, exist_ok=True)

    # 1. Export PyTorch checkpoint -> ONNX
    model = ORTModelForSequenceClassification.from_pretrained(
        SOURCE_MODEL_DIR, export=True
    )
    tokenizer = AutoTokenizer.from_pretrained(SOURCE_MODEL_DIR)
    model.save_pretrained(ONNX_DIR)
    tokenizer.save_pretrained(ONNX_DIR)

    # 2. Apply dynamic int8 quantization on the ONNX graph
    quantizer = ORTQuantizer.from_pretrained(ONNX_DIR)
    qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=QUANTIZED_DIR, quantization_config=qconfig)
    tokenizer.save_pretrained(QUANTIZED_DIR)

    print(f"Quantized model saved to {QUANTIZED_DIR}")

if __name__ == "__main__":
    main()