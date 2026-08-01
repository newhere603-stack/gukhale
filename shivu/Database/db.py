import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv(
    "MONGO_URL",
    "mongodb+srv://teamdaxx123:teamdaxx123@cluster0.ysbpgcp.mongodb.net/?retryWrites=true&w=majority",
)
DB_NAME = os.getenv("DB_NAME", "GRABBING_YOUR_WAIFU")

db_client = None

def get_db():
    global db_client
    if db_client is None:
        db_client = AsyncIOMotorClient(MONGO_URI)
    return db_client[DB_NAME]

class LazyCollection:
    def __init__(self, name):
        self.name = name

    @property
    def col(self):
        return get_db()[self.name]

    async def find_one(self, *args, **kwargs):
        return await self.col.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return await self.col.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return await self.col.update_one(*args, **kwargs)

user_collection = LazyCollection("users")
