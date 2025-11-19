from pymongo import MongoClient

client = MongoClient("SUA_URL")
db = client["botdiscord"]
col = db["users"]

print("Total documentos:", col.count_documents({}))

print(list(col.find().limit(5)))
