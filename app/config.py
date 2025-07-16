import os
from dotenv import load_dotenv

load_dotenv()

class Config:

    # for open ai embeddings (used by FAISS vector store)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # for groq chat model
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = "llama-3.1-8b-instant"  
    GROQ_API_BASE = "https://api.groq.com/openai/v1"

    # path to hotel faq data
    CSV_DATA_PATH = "data/hotel_faq.csv"
