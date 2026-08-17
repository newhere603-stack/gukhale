from motor.motor_asyncio import AsyncIOMotorClient
import os
from shivu import LOGGER

# Heroku optimized MongoDB URI
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# 🔥 High-Performance Client Setup for Heroku
client = AsyncIOMotorClient(
    MONGO_URI,
    maxPoolSize=50,                # Handles multiple concurrent user requests smoothly
    minPoolSize=10,                # Keeps connections warm to eliminate connection delay
    serverSelectionTimeoutMS=5000, # Fails fast if network drops instead of hanging
    connectTimeoutMS=10000         # Optimized for cloud hosting network latency
)

db = client[DB_NAME]
collection = db[COLLECTION_NAME]

async def init_db_indexes():
    """Bot start hote hi index bana dega taaki search 0.01s mein ho."""
    try:
        await collection.create_index("user_id", unique=True)
        LOGGER.info("⚡ Database Index for 'user_id' created successfully.")
    except Exception as e:
        LOGGER.error(f"Failed to create index: {e}")

# --- Fast Async Database Functions ---
async def get_user_data(user_id):
    """Lightning-fast user lookup."""
    return await collection.find_one({"user_id": user_id})

async def save_user_data(user_id, user_data):
    """Optimized atomic upsert operation."""
    await collection.update_one(
        {"user_id": user_id}, 
        {"$set": user_data}, 
        upsert=True
    )
