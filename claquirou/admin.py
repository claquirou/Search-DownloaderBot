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
from claquirou.constant import PARAMS, EN_TIPS, FR_TIPS, LOG_FILE


""" Use this if you want to run locally but fill in the token.ini file first """
# config = configparser.ConfigParser()
# config.read(PARAMS)

# API_ID = config["DEFAULT"]["API_ID"]
# API_HASH = config["DEFAULT"]["API_HASH"]
# TOKEN = config["DEFAULT"]["TOKEN"]
# ADMIN_ID = int(config["ADMIN"]["ID"])

# client = TelegramClient(None, int(API_ID), API_HASH).start(bot_token=TOKEN)


""" Use this if you want to deploy the bot"""
API_ID = os.environ["API_ID"]
API_HASH = os.environ["API_HASH"]
TOKEN = os.environ["TOKEN"]
SESSION = os.environ["SESSION"]
ADMIN_ID = os.environ["ADMIN"]

client = TelegramClient(StringSession(SESSION), int(API_ID), API_HASH).start(bot_token=TOKEN)


def create_log():
    if not os.path.exists(LOG_FILE):
        os.makedirs("log", exist_ok=True)
        
def new_logger(user_id):
    create_log()

    logger = logging.Logger("")
    save = logging.FileHandler(LOG_FILE)
    logger.setLevel(logging.DEBUG)
    save.setLevel(level=logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("\n%(asctime)s --> [%(levelname)s] <%(id)s>: %(message)s")
    
    handler.setFormatter(formatter)
    save.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(save)
    logaugment.set(logger, id=str(user_id))

    return logger


def get_tip(lang, tips):
    if lang == "EN":
        with open(EN_TIPS, "r") as f:
            data = json.load(f)
    else:
        with open(FR_TIPS, "r") as f:
            data = json.load(f)

    return data.get(tips)


async def typing_action(chat_id, chat_action="typing", period=3):
    async with client.action(chat_id, chat_action):
        await asyncio.sleep(period)


async def get_user_id():
    database = UserBot()
    get_user = await database.select_data
    return [i[0] for i in get_user]


async def user_lang(user_id):
    database = UserBot()
    user = await database.get_lang(user_id)

    for i in user:
        return str(i[0])


async def send_user():
    database = UserBot()
    get_user = await database.select_data
    users = []
    for i in get_user:
        info = {"ID": i[0], "Nom": i[1], "Prenom": i[2], "Langue": i[3]}
        users.append(info)

    with open("user.json", "w") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


async def new_user(chat_id, first_name, last_name, language):
    database = UserBot()
    all_users = await get_user_id()

    if chat_id not in all_users:
        await database.add_data(chat_id, first_name, last_name, language)
        info = f"NEW USER\n\n**ID**: {chat_id}\n**Nom**: {first_name}\n**Prénom**: {last_name}\n**Langue**: {language}"

        new_logger(chat_id).info("NOUVEL UTILISATEUR ajouté à la base de donnée.")
    else:
        await database.update_data(chat_id, language)
        info = f"UPDATED\n\nID: {chat_id}\nLanguage: {language}"

        new_logger(chat_id).info(f"UPDATED LANG: {language}")

    await database.commit_data
    await client.send_message(int(ADMIN_ID), info)


@client.on(events.NewMessage(pattern="/users"))
async def user(event):
    chat_id = event.chat_id
    await typing_action(chat_id)
    if chat_id != int(ADMIN_ID):
        await event.respond("Vous n'êtes pas autorisé à utiliser cette commande.")
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
        await event.respond("Vous n'êtes pas autorisé à utiliser cette commande.")
        return

    get_user = await database.select_data
    i = 0
    for _ in get_user:
        i += 1

    await client.send_message(chat_id, f"Le bot compte au total {i} utilisateurs.")


# Send log file
@client.on(events.NewMessage(pattern="/userLog"))
async def user_count(event):
    chat_id = event.chat_id
    await typing_action(chat_id)
    if chat_id != int(ADMIN_ID):
        await event.respond("Vous n'êtes pas autorisé à utiliser cette commande.")
        return 

    await client.send_file(chat_id, LOG_FILE)


# Delete log file
@client.on(events.NewMessage(pattern="/deleteLog"))
async def user_count(event):
    chat_id = event.chat_id

    await typing_action(chat_id)
    if chat_id != int(ADMIN_ID):
        await event.respond("Vous n'êtes pas autorisé à utiliser cette commande.")
    else:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            new_logger(chat_id).info("LOG FILE DELETED")
        
            await client.send_message(chat_id, "Le fichier log a bien été supprimé.")
           
        else:
            await client.send_message(chat_id, "Aucun fichier n'a été trouvé...")