import logging  # 🔥 FIX: 'import' ka 'i' small kar diya hai taaki syntax error na aaye
import os
from pyrogram import Client 
from telegram.ext import Application, PicklePersistence
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)

logging.getLogger("apscheduler").setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger("pyrate_limiter").setLevel(logging.ERROR)
LOGGER = logging.getLogger(__name__)

from shivu.config import Development as Config

api_id = Config.api_id
api_hash = Config.api_hash
TOKEN = Config.TOKEN
GROUP_ID = Config.GROUP_ID
CHARA_CHANNEL_ID = Config.CHARA_CHANNEL_ID 
mongo_url = Config.mongo_url 
PHOTO_URL = Config.PHOTO_URL 
SUPPORT_CHAT = Config.SUPPORT_CHAT 
UPDATE_CHAT = Config.UPDATE_CHAT
BOT_USERNAME = Config.BOT_USERNAME 
sudo_users = Config.sudo_users
OWNER_ID = Config.OWNER_ID 
JOINLOGS = "-1003893927065"
LEAVELOGS = "-1003893927065"

# 🔥 YADDASHT (PERSISTENCE) SETUP: Restart hone par session aur menu states bachane ke liye
persistence = PicklePersistence(filepath="bot_persistence_data.pickle")
application = Application.builder().token(TOKEN).persistence(persistence).build()

shivuu = Client("Shivu", api_id=api_id, api_hash=api_hash, bot_token=TOKEN)

# ==========================================
# 1. MAIN DATABASE (Harem, Economy, Settings - via config.py mongo_url)
# ==========================================
# 🔥 FIX: Super Fast Connection Pooling for Main DB
eco_client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=200,
    minPoolSize=20,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    waitQueueTimeoutMS=3000
)
eco_db = eco_client['Character_catcher']

# ==========================================
# 2. GLOBAL CHARACTER DATABASE (New Cluster)
# ==========================================
# 🔥 FIX: Yahan tera NAYA database URL update kar diya gaya hai!
CHARA_MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://newhere603_db_user:0nI0LwDqmctiXmi4@cluster0.enqfatp.mongodb.net/?appName=Cluster0")

# 🔥 FIX: Super Fast Connection Pooling for Characters DB
chara_client = AsyncIOMotorClient(
    CHARA_MONGO_URI,
    maxPoolSize=200,
    minPoolSize=20,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    waitQueueTimeoutMS=3000
)
chara_db = chara_client['GRABBING_YOUR_WAIFU']

# --- COLLECTIONS MAPPING ---
db = eco_db 

# 🔥 Harem aur player data Main DB me set kar diya
user_collection = eco_db["user_collection_lmaoooo"] 

# 🔥 FIX: 'users' ko hata kar sahi collection 'anime_characters_lol' set kiya hai
collection = chara_db['anime_characters_lol'] 

# Economy aur baki sab kuch Main DB me rahega
eco_collection = eco_db['economy_users'] 

set_on_data = eco_db['set_on_data']
refeer_collection = eco_db['refeer_collection']
set_off_data = eco_db['set_off_data']
safari_cooldown_collection = eco_db["safari_cooldown"]
safari_users_collection = eco_db["safari_users_collection"]
sudo_users_collection = eco_db["sudos"]
user_totals_collection = eco_db['user_totals_lmaoooo']
global_ban_users_collection = eco_db["global_ban_users_collection"]
group_user_totals_collection = eco_db['group_user_totalsssssss']
top_global_groups_collection = eco_db['top_global_groups']
pm_users = eco_db['total_pm_users']
banned_groups_collection = eco_db['Banned_Groups']
BANNED_USERS = eco_db['Banned_Users']
registered_users = eco_db['registered_users']
