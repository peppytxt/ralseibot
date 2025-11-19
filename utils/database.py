# =====================
# === File: utils/database.py
# =====================
from pymongo import MongoClient
import os

mongo_url = os.getenv("MONGO_URL")
client = MongoClient(mongo_url)

db = client["ralsei_bot"]   # nome do banco
users = db["users"]         # coleção (tabela)
