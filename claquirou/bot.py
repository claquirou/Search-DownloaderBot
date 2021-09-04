import signal
import time
import asyncio

from telethon import Button, events
from telethon.errors import AlreadyInConversationError

from .admin import client, typing_action, get_user_id, new_logger, get_tip, new_user
from .image import send_images
from .search import Search, Weather
from worker.download import send_files, shutdown


@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    all_users = await get_user_id()

    user = event.chat
    await typing_action(event.chat_id)

    now = time.strftime("%H", time.gmtime())
    greeting = "Bonjour" if 4 < int(now) < 18 else "Bonsoir"

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
    new_logger(chat_id).debug("HELP")

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
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip("WEB"), search=search))

    elif event.data == b"2":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip("IMAGE"), search="image"))

    elif event.data == b"3":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip("AUDIO"), cmd="a"))

    elif event.data == b"4":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip("VIDEO"), cmd="v"))

    elif event.data == b"5":
        await event.delete()
        weather = Weather()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip("METEO"), search=weather))

    raise events.StopPropagation


async def user_conversation(chat_id, tips, search=None, cmd=None):
    out = 900 if chat_id in [1468858929, 984343307, 1899051788] else 65
    
    try:
        async with client.conversation(chat_id, timeout=out) as conv:
            msg = "\n\nPour mettre fin à la conversation et choisir une autre option, appuyez sur **/end**.\n\nNB: Le bot n'est plus maintenue depuis le 05/09/2020"
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
                                except:
                                    result = search.other_result(response.raw_text)
                                    await conv.send_message(result)

                        else:
                            try:
                                await send_files(client=client, chat_id=chat_id, message=response.raw_text, cmd=cmd,
                                                 log=new_logger(chat_id))
                            except Exception as e:
                                await client.send_message(chat_id, f"Rappel: Le bot n'est plus maintenue depuis le 05/09/2020\n\n{str(e)}")

                    else:
                        await conv.send_message(get_tip("END"))
                        continue_conv = False

            except asyncio.TimeoutError:
                await conv.send_message("Conversation terminée!\n\nPour afficher les options appuyez sur **/options**.\n\nNB: Le bot n'est plus maintenue depuis le 05/09/2020 et ne serait donc plus mis à jour.")

    except AlreadyInConversationError:
        await client.send_message(chat_id, get_tip("TIPS"))


@client.on(events.NewMessage)
async def media(event):
    if event.file:
        await event.reply(
            "Types de fichiers non pris en charge pour le moment. Ressayez plus tard...\n\nAppuyez sur **/options** "
            "pour afficher les options.",
            parse_mode="md")
        new_logger(event.chat_id).debug("FILE")

    elif event.contact:
        await event.respond("Vos contacts doivent rester privés!\n\nAppuyez sur **/options** pour afficher les options.",
                            parse_mode="md")
        new_logger(event.chat_id).debug("CONTACT")


def sig_handler():
    asyncio.run_coroutine_threadsafe(shutdown(client), asyncio.get_event_loop())


def run():
    client.start()
    print("Bot demarré avec succès..")
    asyncio.get_event_loop().add_signal_handler(signal.SIGABRT, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, sig_handler)
    client.run_until_disconnected()
