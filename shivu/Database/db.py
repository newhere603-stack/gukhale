from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

from shivu.config import Development as Config

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. CHARACTER DATABASE (Super-Charged)
# ==========================================
CHARA_MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# 🔥 High-Performance Client Setup (Max Pool & Fast Timeouts)
chara_client = AsyncIOMotorClient(
    CHARA_MONGO_URI,
    maxPoolSize=200,          # Massive concurrent traffic handle karne ke liye
    minPoolSize=20,           # Connections hamesha warm rahenge
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    waitQueueTimeoutMS=3000
)

chara_db = chara_client[DB_NAME]
collection = chara_db[COLLECTION_NAME]

# ==========================================
# 2. ECONOMY DATABASE (Super-Charged)
# ==========================================
ECO_MONGO_URI = Config.mongo_url

eco_client = AsyncIOMotorClient(
    ECO_MONGO_URI,
    maxPoolSize=200,
    minPoolSize=20,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    waitQueueTimeoutMS=3000
)

eco_db = eco_client["Waifu_Economy"]
eco_collection = eco_db["economy_users"]


async def init_db_indexes():
    """Bot start hote hi lightning-fast indexes create kar dega."""
    try:
        await collection.create_index("user_id", unique=True, background=True)
        await collection.create_index("id", background=True)  # Quick ID lookups ke liye
        await eco_collection.create_index("id", unique=True, background=True)
        LOGGER.info("⚡ Super-charged Database Indexes created/verified successfully.")
    except Exception as e:
        if "IndexKeySpecsConflict" in str(e):
            LOGGER.info("⚡ Database indexes already verified (conflict ignored safely).")
        else:
            LOGGER.error(f"Failed to create index: {e}")

# --- Lightning-Fast Async Database Functions ---
async def get_user_data(user_id, projection=None):
    """Optimized user lookup with optional projection for blazing fast speed."""
    return await collection.find_one({"user_id": user_id}, projection=projection)

async def save_user_data(user_id, user_data):
    """Optimized atomic upsert operation."""
    await collection.update_one(
        {"user_id": user_id}, 
        {"$set": user_data}, 
        upsert=True
    )
