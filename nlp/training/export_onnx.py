"""
Exports the trained 10-intent classifier to ONNX,
then applies dynamic int8 quantization for deployment.
"""

from pathlib import Path

from optimum.onnxruntime import ORTModelForSequenceClassification
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from optimum.onnxruntime import ORTQuantizer
from transformers import AutoTokenizer


# Correct newly trained 10-intent checkpoint
SOURCE_MODEL_DIR = "nlp/results/checkpoint-1976"

# Existing model directory containing the compatible tokenizer
TOKENIZER_SOURCE_DIR = "nlp/exports/best_model"

# Export destinations
ONNX_DIR = "nlp/exports/onnx_model"
QUANTIZED_DIR = "nlp/exports/quantized_model"


def main():

    print("=" * 70)
    print("InfoByte 10-Intent Model Export")
    print("=" * 70)

    print(f"\nSource model:     {SOURCE_MODEL_DIR}")
    print(f"Tokenizer source: {TOKENIZER_SOURCE_DIR}")
    print(f"ONNX output:      {ONNX_DIR}")
    print(f"Quantized output: {QUANTIZED_DIR}")

    Path(ONNX_DIR).mkdir(parents=True, exist_ok=True)
    Path(QUANTIZED_DIR).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # 1. Export trained checkpoint to ONNX
    # ---------------------------------------------------------

    print("\n[1/4] Exporting trained 10-intent model to ONNX...")

    model = ORTModelForSequenceClassification.from_pretrained(
        SOURCE_MODEL_DIR,
        export=True
    )

    print("ONNX model exported successfully.")

    # ---------------------------------------------------------
    # 2. Load tokenizer
    # ---------------------------------------------------------

    print("\n[2/4] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_SOURCE_DIR
    )

    print("Tokenizer loaded successfully.")

    # ---------------------------------------------------------
    # 3. Save ONNX model + tokenizer
    # ---------------------------------------------------------

    print("\n[3/4] Saving ONNX model and tokenizer...")

    model.save_pretrained(ONNX_DIR)
    tokenizer.save_pretrained(ONNX_DIR)

    print(f"ONNX model saved to: {ONNX_DIR}")

    # ---------------------------------------------------------
    # 4. Quantize ONNX model
    # ---------------------------------------------------------

    print("\n[4/4] Quantizing ONNX model...")

    quantizer = ORTQuantizer.from_pretrained(ONNX_DIR)

    qconfig = AutoQuantizationConfig.avx512_vnni(
        is_static=False,
        per_channel=False
    )

    quantizer.quantize(
        save_dir=QUANTIZED_DIR,
        quantization_config=qconfig
    )

    # Save tokenizer alongside quantized model
    tokenizer.save_pretrained(QUANTIZED_DIR)

    print("\n" + "=" * 70)
    print("EXPORT COMPLETE")
    print("=" * 70)

    print(f"\nQuantized 10-intent model saved to:")
    print(QUANTIZED_DIR)

    print("\nNext verify the model with:")
    print(
        "cat nlp/exports/quantized_model/config.json "
        "| grep -A 25 '\"id2label\"'"
    )


if __name__ == "__main__":
    main()