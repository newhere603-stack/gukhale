import os
from motor.motor_asyncio import AsyncIOMotorClient

# Environment variables se Mongo details fetch karna
MONGO_URI = os.getenv(
    "MONGO_URL",
    "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority",
)
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")

# Async Motor Client connection
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
user_collection = db["users"]


async def get_user(uid):
    return await user_collection.find_one({"id": uid})


async def init_user(uid):
    user = {"id": uid, "balance": 0}
    await user_collection.insert_one(user)
    return user


async def save_user_data(user_id, user_data):
    await user_collection.update_one(
        {"id": user_id}, {"$set": user_data}, upsert=True
    )
