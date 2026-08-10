from motor.motor_asyncio import AsyncIOMotorClient
import os

# Tera original MongoDB URL
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# Async client setup (Bot fast karne ke liye)
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# Async functions
async def get_user_data(user_id):
    return await collection.find_one({"user_id": user_id})

async def save_user_data(user_id, user_data):
    await collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)
    print("User data saved successfully.")
