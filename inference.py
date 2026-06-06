import os
import time
import numpy as np
from pathlib import Path
from PIL import Image

# Setup paths relative to root of MobiKD project
BACKEND_DIR = Path(__file__).parent
ROOT = BACKEND_DIR.parent
MODELS_DIR = ROOT / "models"

LEAF_MODEL_PATH = MODELS_DIR / "leaf_validator" / "kd_mobilenetv2_leaf_validator_float16.tflite"
DISEASE_MODEL_PATH = MODELS_DIR / "potato_disease" / "kd_mobilenetv2_potato_disease_float16.tflite"

LEAF_CLASSES = ["not_leaf", "leaf"]
DISEASE_CLASSES = ["early_blight", "healthy", "late_blight", "not_potato_leaf"]

LEAF_SIZE = 32
DISEASE_SIZE = 96
LEAF_THRESHOLD = 0.50  # Match mobile client threshold (0.50)

# Lazy variables for interpreters
_leaf_interpreter = None
_disease_interpreter = None
_leaf_inp, _leaf_out = None, None
_disease_inp, _disease_out = None, None

def load_tflite_interpreter(model_path: Path):
    try:
        import tflite_runtime.interpreter as tflite
        return tflite.Interpreter(model_path=str(model_path))
    except ImportError:
        pass
    try:
        import tensorflow as tf
        return tf.lite.Interpreter(model_path=str(model_path))
    except ImportError:
        raise RuntimeError("Neither tflite_runtime nor tensorflow found in the environment. Install with: pip install tflite-runtime")

def init_models():
    global _leaf_interpreter, _disease_interpreter, _leaf_inp, _leaf_out, _disease_inp, _disease_out
    
    if _leaf_interpreter is not None:
        return
        
    print(f"Loading Stage 1 Leaf Validator: {LEAF_MODEL_PATH}")
    _leaf_interpreter = load_tflite_interpreter(LEAF_MODEL_PATH)
    _leaf_interpreter.allocate_tensors()
    _leaf_inp = _leaf_interpreter.get_input_details()
    _leaf_out = _leaf_interpreter.get_output_details()
    
    print(f"Loading Stage 2 Disease Detector: {DISEASE_MODEL_PATH}")
    _disease_interpreter = load_tflite_interpreter(DISEASE_MODEL_PATH)
    _disease_interpreter.allocate_tensors()
    _disease_inp = _disease_interpreter.get_input_details()
    _disease_out = _disease_interpreter.get_output_details()

def preprocess_image(img: Image.Image, size: int) -> np.ndarray:
    # Convert to RGB
    img = img.convert("RGB")
    
    # Centre crop to square
    w, h = img.size
    m = min(w, h)
    img = img.crop(((w - m) // 2, (h - m) // 2, (w + m) // 2, (h + m) // 2))
    
    # Resize to model input size
    # Try using Bilinear interpolation
    try:
        resample_method = Image.Resampling.BILINEAR
    except AttributeError:
        resample_method = Image.BILINEAR
        
    img = img.resize((size, size), resample_method)
    
    # Normalize pixel values to [0, 1]
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # Add batch dimension: (1, size, size, 3)

def run_inference(interpreter, inp_details, out_details, data: np.ndarray) -> np.ndarray:
    interpreter.set_tensor(inp_details[0]["index"], data)
    interpreter.invoke()
    return interpreter.get_tensor(out_details[0]["index"])[0]

def analyze_leaf_image(img: Image.Image) -> dict:
    """
    Runs the 2-stage MobiKD analysis pipeline on a PIL Image.
    """
    init_models()
    
    # Stage 1: Leaf Validator
    t0 = time.time()
    leaf_data = preprocess_image(img, LEAF_SIZE)
    leaf_probs = run_inference(_leaf_interpreter, _leaf_inp, _leaf_out, leaf_data)
    t1 = (time.time() - t0) * 1000
    
    leaf_idx = int(np.argmax(leaf_probs))
    leaf_conf = float(leaf_probs[leaf_idx])
    leaf_label = LEAF_CLASSES[leaf_idx]
    
    # If not a leaf or confidence below threshold, reject early
    if leaf_label == "not_leaf" or leaf_conf < LEAF_THRESHOLD:
        return {
            "stage1Label": "not_leaf",
            "stage1Confidence": leaf_conf,
            "stage2Label": None,
            "stage2Confidence": None,
            "latencyMs": t1
        }
        
    # Stage 2: Potato Disease Detector
    t0_stage2 = time.time()
    disease_data = preprocess_image(img, DISEASE_SIZE)
    disease_probs = run_inference(_disease_interpreter, _disease_inp, _disease_out, disease_data)
    t2 = (time.time() - t0_stage2) * 1000
    
    disease_idx = int(np.argmax(disease_probs))
    disease_conf = float(disease_probs[disease_idx])
    disease_label = DISEASE_CLASSES[disease_idx]
    
    return {
        "stage1Label": "leaf",
        "stage1Confidence": leaf_conf,
        "stage2Label": disease_label,
        "stage2Confidence": disease_conf,
        "latencyMs": t1 + t2
    }
