# =====================
# === File: utils/database.py
# =====================
from pymongo import MongoClient
import os

mongo_url = os.getenv("MONGO_URL")
client = MongoClient(mongo_url)

db = client["ralsei_bot"]   # nome do banco
<<<<<<< HEAD
users = db["users"]         # coleção (tabela)
=======
users = db["users"]         # coleção (tabela)
>>>>>>> 12010c046fcfe41a40ed3b8e06359cb888a5be3d
