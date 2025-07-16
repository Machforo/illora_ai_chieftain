import os
import joblib

# Load pipeline 
MODEL_PATH = "C:\\Users\\Atharv\\Documents\\AI_chieftain_bot_AtharvKumar\\intent_classifier_model.pkl"
pipeline = joblib.load(MODEL_PATH)

def classify_intent(text: str) -> str:
    """Return predicted intent for a given text."""
    return pipeline.predict([text])[0]

