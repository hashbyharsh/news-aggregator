import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GROQ_BASE_URL = "https://api.groq.com"

    NEWS_SOURCES = [
        "https://auto.economictimes.indiatimes.com",
        "https://www.autocarindia.com/car-news",
        "https://www.rushlane.com",
        "https://gaadiwaadi.com",
        "https://www.autocarpro.in/news",
        "https://auto.hindustantimes.com/auto/cars"
    ]
    
    NEWS_TOPIC = "car"

config = Config()
