import asyncio
import json
import logging
import os
import sys

import logaugment
from telethon import events

from .constant import EN_TIPS, FR_TIPS, LOG_FILE
from .credential import client, ADMIN_ID
from .users import UserBot


def create_log():
    if not os.path.exists(LOG_FILE):
        os.makedirs(".log", exist_ok=True)


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
    language = await database.get_lang(user_id)

    for i in language:
        return str(i[0])


async def _send_user():
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
    all_usr = await get_user_id()

    if chat_id not in all_usr:
        await database.add_data(chat_id, first_name, last_name, language)
        info = f"NEW USER\n\n**ID**: {chat_id}\n**Nom**: {first_name}\n**Prénom**: {last_name}\n**Langue**: {language}"

        new_logger(chat_id).info("NOUVEL UTILISATEUR ajouté à la base de donnée.")
    else:
        await database.update_data(chat_id, language)
        info = f"UPDATED\n\nID: {chat_id}\nLanguage: {language}"

        new_logger(chat_id).info(f"UPDATED LANG: {language}")

    await database.commit_data
    for i in ADMIN_ID:
        try:
            await client.send_message(i, info)
        except ValueError:
            continue

    return


async def _authorized_user(event):
    checked = True

    if event.chat_id not in ADMIN_ID:
        checked = False
        await event.respond("Vous n'êtes pas autorisé à utiliser cette commande.")

    return checked


# async def user_blocked(event):
#     button = Button.url("CONTACT BOT ADMIN", url="https://t.me/claquirou")
#
#     if event.chat_id in USER_BLOCKED:
#         message = "Désolé, vous ne pouvez pas utiliser le bot car vous avez été bloqué."
#         await client.send_message(event.chat_id, message, buttons=button)
#         return


@client.on(events.NewMessage(pattern="/users"))
async def all_users(event):
    await typing_action(event.chat_id)
    if await _authorized_user(event):
        await _send_user()
        await client.send_file(event.chat_id, "user.json")
        os.remove("user.json")
        return


@client.on(events.NewMessage(pattern="/userCount"))
async def user_count(event):
    database = UserBot()

    await typing_action(event.chat_id)
    if await _authorized_user(event):
        get_user = await database.select_data
        i = sum(1 for _ in get_user)
        await event.respond(f"Le bot compte au total {i} utilisateurs.")
        return


# Send log file
@client.on(events.NewMessage(pattern="/userLog"))
async def user_log(event):
    await typing_action(event.chat_id)
    if await _authorized_user(event):
        await client.send_file(event.chat_id, LOG_FILE)
        return


# Delete log file
@client.on(events.NewMessage(pattern="/deleteLog"))
async def delete_log(event):
    chat_id = event.chat_id

    await typing_action(chat_id)
    if await _authorized_user(event):
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            new_logger(chat_id).info("LOG FILE DELETED")

            await event.respond("Le fichier log a bien été supprimé.")

        else:
            await event.respond("Aucun fichier n'a été trouvé...")

        return
