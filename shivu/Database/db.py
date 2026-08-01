import os
from motor.motor_asyncio import AsyncIOMotorClient

# 1. MONGO_URI setup: os.getenv me pehle environment variable ka naam aata hai, default value second parameter hoti hai
MONGO_URI = os.getenv(
    "MONGO_URL",
    "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority",
)
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# 2. Async Client Connection
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
user_collection = db[COLLECTION_NAME]


# 3. Functions ko async/await kar diya gaya hai
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
    print("User data saved successfully.")
