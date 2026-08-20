from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# 🔥 Sahi path se Config ko import kiya taaki Heroku par "ModuleNotFoundError" na aaye
from shivu.config import Development as Config

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. CHARACTER DATABASE (Purana Wala - Characters Safe Hain)
# ==========================================
CHARA_MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# 🔥 High-Performance Client Setup
chara_client = AsyncIOMotorClient(
    CHARA_MONGO_URI,
    maxPoolSize=50,
    minPoolSize=10,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000
)

chara_db = chara_client[DB_NAME]
collection = chara_db[COLLECTION_NAME] # Ise 'collection' hi rakha hai taaki baaki codes break na hon

# ==========================================
# 2. ECONOMY DATABASE (Naya Wala - config.py se)
# ==========================================
ECO_MONGO_URI = Config.mongo_url

eco_client = AsyncIOMotorClient(
    ECO_MONGO_URI,
    maxPoolSize=50,
    minPoolSize=10,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000
)

eco_db = eco_client["Waifu_Economy"]
eco_collection = eco_db["economy_users"] # Ye collection sirf coins/tokens ke liye use hoga


async def init_db_indexes():
    """Bot start hote hi dono database ke index bana dega taaki search lightning fast ho."""
    try:
        # Character DB index with background=True to prevent conflicts
        await collection.create_index("user_id", unique=True, background=True)
        # Economy DB index
        await eco_collection.create_index("id", unique=True, background=True)
        LOGGER.info("⚡ Both Database Indexes for 'user_id' & 'id' created/verified successfully.")
    except Exception as e:
        # Agar index pehle se bana hai toh ignore karega taaki logs clean rahein
        if "IndexKeySpecsConflict" in str(e):
            LOGGER.info("⚡ Database indexes already verified (conflict ignored safely).")
        else:
            LOGGER.error(f"Failed to create index: {e}")

# --- Fast Async Database Functions (For Characters) ---
async def get_user_data(user_id):
    """Lightning-fast user lookup for characters."""
    return await collection.find_one({"user_id": user_id})

async def save_user_data(user_id, user_data):
    """Optimized atomic upsert operation for characters."""
    await collection.update_one(
        {"user_id": user_id}, 
        {"$set": user_data}, 
        upsert=True
    )
