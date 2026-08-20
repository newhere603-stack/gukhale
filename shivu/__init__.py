import logging  
import os
from pyrogram import Client 
from telegram.ext import Application
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

application = Application.builder().token(TOKEN).build()
shivuu = Client("Shivu", api_id, api_hash, bot_token=TOKEN)

# ==========================================
# 1. MAIN DATABASE (Harem, Economy, Settings - via config.py mongo_url)
# ==========================================
eco_client = AsyncIOMotorClient(mongo_url)
eco_db = eco_client['Character_catcher']

# ==========================================
# 2. GLOBAL CHARACTER DATABASE (teamdaxx123 cluster)
# ==========================================
CHARA_MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority")
chara_client = AsyncIOMotorClient(CHARA_MONGO_URI)
chara_db = chara_client['GRABBING_YOUR_WAIFU']

# --- COLLECTIONS MAPPING ---
db = eco_db 

# 🔥 FIX: Harem aur player data wapas Main DB me set kar diya
user_collection = eco_db["user_collection_lmaoooo"] 

# 🔥 FIX: Global Characters wali collection teamdaxx123 se aayegi
collection = chara_db['users'] 

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
