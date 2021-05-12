import configparser
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

from .constant import PARAMS


ADMIN_ID = [1468858929]
USER_BLOCKED = []


config = configparser.ConfigParser()
config.read(PARAMS)

try :
    API_ID = config["DEFAULT"]["API_ID"]
    API_HASH = config["DEFAULT"]["API_HASH"]
    TOKEN = config["DEFAULT"]["TOKEN"]
    DATABASE = config["DEFAULT"]["DATABASE_URL"]
    SESSION = os.environ["SESSION"]
except KeyError:
    SESSION = ""

client = TelegramClient(StringSession(SESSION), int(API_ID), API_HASH).start(bot_token=TOKEN)
# client = TelegramClient(None, int(API_ID), API_HASH).start(bot_token=TOKEN)
