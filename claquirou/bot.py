import configparser
import json
import logging
import os
import signal
import sys
import time
import asyncio

import logaugment
from telethon import Button, TelegramClient, events
from telethon.errors import AlreadyInConversationError
from telethon.sessions import StringSession

from claquirou.constant import PARAMS, TIPS_DIR
from claquirou.image import send_images
from claquirou.search import Search, Weather
from claquirou.users import UserBot
from worker.download import send_files, shutdown

config = configparser.ConfigParser()
config.read(PARAMS)

API_ID = config["DEFAULT"]["API_ID"]
API_HASH = config["DEFAULT"]["API_HASH"]
TOKEN = config["DEFAULT"]["TOKEN"]

# API_ID = os.environ["API_ID"]
# API_HASH = os.environ["API_HASH"]
# TOKEN = os.environ["TOKEN"]
# SESSION = os.environ["SESSION"]

ADMIN_ID = [711322052]

# client = TelegramClient(StringSession(SESSION), int(API_ID), API_HASH).start(bot_token=TOKEN)


client = TelegramClient(None, int(API_ID), API_HASH).start(bot_token=TOKEN)


def new_logger(user):
    logger = logging.Logger("")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(levelname)s] <%(id)s>: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logaugment.set(logger, id=str(user))

    return logger


async def typing_action(chat_id, chat_action="typing", period=3):
    async with client.action(chat_id, chat_action):
        await asyncio.sleep(period)


@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    all_users = await user_id()

    user = event.chat
    await typing_action(event.chat_id)

    now = time.strftime("%H", time.gmtime())
    if 4 < int(now) < 18:
        greeting = "Bonjour"
    else:
        greeting = "Bonsoir"

    if user.id not in all_users:
        start_msg = get_tip("START")
        message = f"{greeting} {user.first_name}.\n{start_msg}"

        await event.respond(message)
        await new_user(user.id, user.first_name, user.last_name)

    else:
        await event.respond(
            f"{greeting} {user.first_name}.\nPour mettre fin à une conversation appuyez sur **/end** avant de cliquer "
            f"sur "
            f"**/options** pour choisir d'autre options. Pour avoir de l'aide, appuyez sur **/help**.")

    raise events.StopPropagation


@client.on(events.NewMessage(pattern="/help"))
async def helps(event):
    chat_id = event.chat_id
    new_logger(chat_id).debug("Demande de l'aide")

    await typing_action(chat_id)
    with open("help.txt", "r") as f:
        data = f.read()

    await event.respond(data)
    raise events.StopPropagation


@client.on(events.NewMessage(pattern="/options"))
async def option(event):
    user = event.chat
    chat_id = event.chat_id
    await new_user(chat_id, user.first_name, user.last_name)

    keyboard = [
        [Button.inline("Recherche Web🌍", b"1"),
         Button.inline("Recherche d'Image📸", b"2")],

        [Button.inline("Audio🎧", b"3"),
         Button.inline("Vidéos🎥", b"4")],

        [Button.inline("Données Métérologiques🌦", b"5")]
    ]

    await client.send_message(chat_id, "Choississez une option:", buttons=keyboard)

    raise events.StopPropagation


loop = asyncio.get_event_loop()


@client.on(events.CallbackQuery)
async def button(event):
    chat_id = event.chat_id

    if event.data == b"1":
        await event.delete()
        search = Search()
        await user_conversation(chat_id=chat_id, tips=get_tip("WEB"), search=search)

    elif event.data == b"2":
        await event.delete()
        await user_conversation(chat_id=chat_id, tips=get_tip("IMAGE"), search="image")

    elif event.data == b"3":
        await event.delete()
        await user_conversation(chat_id=chat_id, tips=get_tip("AUDIO"), cmd="a")

    elif event.data == b"4":
        await event.delete()
        await user_conversation(chat_id=chat_id, tips=get_tip("VIDEO"), cmd="v")

    elif event.data == b"5":
        await event.delete()
        weather = Weather()
        await user_conversation(chat_id=chat_id, tips=get_tip("METEO"), search=weather)

    raise events.StopPropagation


async def user_conversation(chat_id, tips, search=None, cmd=None):
    try:
        async with client.conversation(chat_id, timeout=65) as conv:
            msg = "\n\nPour mettre fin à la conversation et choisir une autre option, appuyez sur **/end** ."
            await conv.send_message(f"{tips} {msg}", parse_mode='md')

            try:
                continue_conv = True

                while continue_conv:
                    response = conv.get_response()
                    response = await response

                    if response.raw_text != "/end":
                        if search is not None:
                            new_logger(chat_id).info(f"RECHERCHE- {response.raw_text}")

                            if search == "image":
                                images = send_images(response.raw_text)
                                number = images[-1]

                                try:
                                    for img in images[0:number]:
                                        await typing_action(chat_id, chat_action="photo", period=1)
                                        try:
                                            await conv.send_file(img)
                                        except:
                                            continue
                                except TypeError:
                                    await conv.send_message(images)

                            else:
                                await typing_action(chat_id, period=5)
                                try:
                                    result = search.results(response.raw_text)
                                    await conv.send_message(result)
                                except ValueError:
                                    result = search.other_result(response.raw_text)
                                    await conv.send_message(result)

                        else:
                            try:
                                await send_files(client=client, chat_id=chat_id, message=response.raw_text, cmd=cmd,
                                            log=new_logger(chat_id))
                            except Exception as e:
                                await client.send_message(chat_id, str(e))

                    else:
                        await conv.send_message(get_tip("END"))
                        continue_conv = False

            except asyncio.TimeoutError:
                await conv.send_message("Conversation terminée!\n\nPour afficher les options appuyez sur **/options**")

    except AlreadyInConversationError:
        await client.send_message(chat_id, get_tip("TIPS"))


@client.on(events.NewMessage)
async def media(event):
    if event.file:
        await event.reply(
            "Types de fichiers non pris en charge pour le moment. Ressayez plus tard...\n\nAppuyez sur **/options** "
            "pour afficher les options",
            parse_mode="md")
        new_logger(event.chat_id).debug("FILE")

    elif event.contact:
        await event.respond("Vos contacts doivent rester privés!\n\nAppuyez sur **/options** pour afficher les options",
                            parse_mode="md")
        new_logger(event.chat_id).debug("CONTACT")


@client.on(events.NewMessage(pattern="/users"))
async def admin(event):
    chat_id = event.chat_id
    await typing_action(chat_id)
    if chat_id not in ADMIN_ID:
        await event.respond("Vous n'êtes pas autorisé à utilisé cette commande.")
        return

    await send_user()
    await client.send_file(chat_id, "user.json")
    os.remove("user.json")

    raise events.StopPropagation


@client.on(events.NewMessage(pattern="/userCount"))
async def user_count(event):
    chat_id = event.chat_id

    await typing_action(chat_id)
    if chat_id not in ADMIN_ID:
        await event.respond("Vous n'êtes pas autorisé à utilisé cette commande.")
        return

    database = await UserBot().select_data
    i = 0
    for _ in database:
        i += 1

    await client.send_message(chat_id, f"Le bot compte au total {i} utilisateurs.")


async def user_id():
    database = UserBot()

    get_user = await database.select_data
    all_user = [i[0] for i in get_user]
    return all_user


async def new_user(chat_id, first_name, last_name):
    database = UserBot()
    all_users = await user_id()

    if chat_id not in all_users:
        await database.add_data(chat_id, first_name, last_name)
        new_logger(chat_id).info("NOUVEL UTILISATEUR ajouté à la base de donnée.")

        await client.send_message(711322052, f"Nouvel utilisateur {chat_id}")


async def send_user():
    database = await UserBot().select_data
    user = []
    for i in database:
        info = {"ID": i[0], "Nom": i[1], "Prenom": i[2]}
        user.append(info)

    with open("user.json", "w") as f:
        json.dump(user, f, indent=4, ensure_ascii=False)


def get_tip(tips):
    with open(TIPS_DIR, "r") as f:
        data = json.load(f)

    return data.get(tips)


def sig_handler():
    asyncio.run_coroutine_threadsafe(shutdown(client), asyncio.get_event_loop())


def run():
    client.start()
    print("Bot demarré avec succès..")
    asyncio.get_event_loop().add_signal_handler(signal.SIGABRT, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, sig_handler)
    client.run_until_disconnected()
