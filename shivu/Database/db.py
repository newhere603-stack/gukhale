from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pymongo.errors import OperationFailure # 🔥 FIX: Better error handling ke liye

from shivu.config import Development as Config

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. CHARACTER DATABASE (Super-Charged)
# ==========================================
# ⚠️ WARNING: Apna database password yahan hardcode mat rakho, env var (MONGO_URI) use karo!
CHARA_MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://itsmefroxy_db_user:82pRCH3TA0sr17iP@cluster0.7s0o0go.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")
COLLECTION_NAME = "users"

# 🔥 High-Performance Client Setup
chara_client = AsyncIOMotorClient(
    CHARA_MONGO_URI,
    maxPoolSize=200,          
    minPoolSize=20,           
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
        # 🔥 FIX: Modern MongoDB mein background=True default hota hai, ise hataya taaki deprecation warnings na aayein
        await collection.create_index("user_id", unique=True)
        await collection.create_index("id") 
        await eco_collection.create_index("id", unique=True)
        LOGGER.info("⚡ Super-charged Database Indexes created/verified successfully.")
    except OperationFailure as e:
        # 🔥 FIX: IndexOptionsConflict ko bhi handle kiya taaki bot crash na ho agar pehle se index alag settings ke sath ho
        if "IndexKeySpecsConflict" in str(e) or "IndexOptionsConflict" in str(e):
            LOGGER.info("⚡ Database indexes already verified (conflict ignored safely).")
        else:
            LOGGER.error(f"Failed to create index: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error while creating index: {e}")

# --- Lightning-Fast Async Database Functions ---
async def get_user_data(user_id, projection=None):
    # 🔥 Read operations automatically un indexes ka use karenge jo upar banaye hain
    return await collection.find_one({"user_id": user_id}, projection=projection)

async def save_user_data(user_id, user_data):
    # 🔥 $set assure karta hai ki sirf specific fields update hon, pura document replace na ho
    await collection.update_one(
        {"user_id": user_id}, 
        {"$set": user_data}, 
        upsert=True
    )
