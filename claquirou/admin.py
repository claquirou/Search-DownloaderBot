import asyncio
import configparser
import json
import logging
import sys
import os

import logaugment
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from claquirou.users import UserBot
from claquirou.constant import PARAMS, TIPS_DIR


config = configparser.ConfigParser()
config.read(PARAMS)

API_ID = config["DEFAULT"]["API_ID"]
API_HASH = config["DEFAULT"]["API_HASH"]
TOKEN = config["DEFAULT"]["TOKEN"]
ADMIN_ID = config["ADMIN"]["ID"]

# sADMIN_ID = os.environ["ADMIN_ID"]
# API_ID = os.environ["API_ID"]
# API_HASH = os.environ["API_HASH"]
# TOKEN = os.environ["TOKEN"]
# SESSION = os.environ["SESSION"]

# client = TelegramClient(StringSession(SESSION), int(API_ID), API_HASH).start(bot_token=TOKEN)
client = TelegramClient(None, int(API_ID), API_HASH).start(bot_token=TOKEN)


def new_logger(user_id):
    logger = logging.Logger("")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(levelname)s] <%(id)s>: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logaugment.set(logger, id=str(user_id))

    return logger


def get_tip(tips):
    with open(TIPS_DIR, "r") as f:
        data = json.load(f)

    return data.get(tips)


async def get_user_id():
    database = UserBot()
    get_user = await database.select_data
    return [i[0] for i in get_user]


async def send_user():
    database = UserBot()
    get_user = await database.select_data
    users = []
    for i in get_user:
        info = {"ID": i[0], "Nom": i[1], "Prenom": i[2]}
        users.append(info)

    with open("user.json", "w") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


async def typing_action(chat_id, chat_action="typing", period=3):
    async with client.action(chat_id, chat_action):
        await asyncio.sleep(period)


async def new_user(chat_id, first_name, last_name):
    database = UserBot()
    all_users = await get_user_id()

    if chat_id not in all_users:
        await database.add_data(chat_id, first_name, last_name)
        new_logger(chat_id).info("NOUVEL UTILISATEUR ajouté à la base de donnée.")

        info = f"Utilisateur {chat_id} ajouté\n\nNom: {first_name}\nPrénom: {last_name}"
        await client.send_message(711322052, info)


@client.on(events.NewMessage(pattern="/users"))
async def user(event):
    chat_id = event.chat_id
    await typing_action(chat_id)
    if chat_id != int(ADMIN_ID):
        await event.respond("Vous n'êtes pas autorisé à utilisé cette commande.")
        return

    await send_user()
    await client.send_file(chat_id, "user.json")
    os.remove("user.json")

    raise events.StopPropagation


@client.on(events.NewMessage(pattern="/userCount"))
async def user_count(event):
    database = UserBot()
    chat_id = event.chat_id

    await typing_action(chat_id)
    if chat_id != int(ADMIN_ID):
        await event.respond("Vous n'êtes pas autorisé à utilisé cette commande.")
        return

    get_user = await database.select_data
    i = 0
    for _ in get_user:
        i += 1

    await client.send_message(chat_id, f"Le bot compte au total {i} utilisateurs.")
