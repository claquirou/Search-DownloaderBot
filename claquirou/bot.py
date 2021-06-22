import signal
import time
import asyncio

from telethon import Button, events
from telethon.errors import AlreadyInConversationError

from claquirou.admin import typing_action, get_user_id, user_lang, new_logger, get_tip, new_user
from claquirou.credential import ADMIN_ID, client
from claquirou.image import send_images
from claquirou.search import Search
from worker.download import send_files, shutdown

LANG = ["FR", "EN"]
ADMIN_ID = [1468858929, 1799126743, 975714395]

fr_msg = "Désolé, ce bot n'est malheureusement plus disponible au grand public et nous vous présentons toutes nos excuses...\nA bientôt😉."
en_msg = "Sorry, this bot is unfortunately no longer available to the general public and we apologize...\nSee you soon😉."


@client.on(events.NewMessage(pattern="/start"))
async def language_choice(event):
    keyboard = [
        [Button.inline("French 🇫🇷", b"10"),
         Button.inline("English 🇺🇸", b"20")],
    ]

    await client.send_message(event.chat_id, "Select language", buttons=keyboard)
    new_logger(event.chat_id).info("USER TO PRESS START")

    raise events.StopPropagation


@client.on(events.CallbackQuery)
async def language_button(event):
    user = event.chat

    if event.data == b"10":
        await event.delete()

        if user.id not in ADMIN_ID:
            await event.respond(fr_msg)
            return
        
        other = get_tip("FR", "OTHER")
        await event.respond(f"Hello {user.first_name}.\n{other}")
        await new_user(user.id, user.first_name, user.last_name, LANG[0])

    elif event.data == b"20":
        await event.delete()

        if user.id not in ADMIN_ID:
            await event.respond(en_msg)
            return
        
        other = get_tip("EN", "OTHER")
        await event.respond(f"Hello {user.first_name}.\n{other}")
        await new_user(user.id, user.first_name, user.last_name, LANG[1])


@client.on(events.NewMessage(pattern="/help"))
async def helps(event):
    chat_id = event.chat_id
    lang = await user_lang(chat_id)

    if chat_id not in ADMIN_ID:
        if lang == LANG[0]:
            await event.respond(fr_msg)
            return

        await event.respond(en_msg)

    else:
        await typing_action(chat_id)
        if lang == LANG[0]:
            with open("claquirou/fr/help.txt", "r") as f:
                data = f.read()
        else:
            with open("claquirou/en/help.txt", "r") as f:
                data = f.read()

        await event.respond(data)
    new_logger(chat_id).debug("USER TO PRESS HELP")
    raise events.StopPropagation


loop = asyncio.get_event_loop()


@client.on(events.NewMessage(pattern="/options"))
async def options(event):
    chat_id = event.chat_id
    lang = await user_lang(chat_id)

    if chat_id not in ADMIN_ID:
        if lang == LANG[0]:
            await event.respond(fr_msg)
            return

        await event.respond(en_msg)

    else:
        keyboard = [
            [Button.inline(get_tip(lang, "CHOICE1"), b"1"),
            Button.inline(get_tip(lang, "CHOICE2"), b"2")],

            [Button.inline(get_tip(lang, "CHOICE3"), b"3"),
            Button.inline(get_tip(lang, "CHOICE4"), b"4")],

            [Button.inline(get_tip(lang, "CHOICE5"), b"5")]
        ]

        loop.create_task(client.send_message(chat_id, get_tip(lang, "SELECT"), buttons=keyboard))
        raise events.StopPropagation


@client.on(events.CallbackQuery)
async def buttons(event):
    chat_id = event.chat_id
    lang = await user_lang(chat_id)

    if event.data == b"1":
        await event.delete()
        search = Search(lang)
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "WEB"), search=search))

    elif event.data == b"2":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "IMAGE"), search="image"))

    elif event.data == b"3":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "AUDIO"), cmd="a"))

    elif event.data == b"4":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "VIDEO"), cmd="v"))

    elif event.data == b"5":
        await event.delete()
        if await user_lang(chat_id) == LANG[0]:
            msg = "Désolé, cette option est momentanément indisponible 😕.\n\n Pour afficher les options, appuyez sur " \
                  "**/options**."
        else:
            msg = "Sorry, this option is temporarily unavailable 😕.\n\nTo view options press **/options**."

        await event.respond(msg)

    raise events.StopPropagation


async def user_conversation(chat_id, tips, search=None, cmd=None):
    out = 600 if chat_id in ADMIN_ID else 120
    lang = await user_lang(chat_id)

    try:
        async with client.conversation(chat_id, timeout=out) as conv:
            end_conv = get_tip(lang, "END_CONV")
            await conv.send_message(f"{tips} \n\n{end_conv}", parse_mode='md')

            try:
                continue_conv = True

                while continue_conv:
                    response = conv.get_response()
                    response = await response

                    if response.raw_text != "/end":
                        if search is not None:
                            new_logger(chat_id).info(f"SEARCH- {response.raw_text}")

                            if search == "image":
                                images = send_images(response.raw_text, lang)
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
                                                 log=new_logger(chat_id), lang=lang)
                            except Exception as e:
                                await client.send_message(chat_id, f"{str(e)}")

                    else:
                        await conv.send_message(get_tip(lang, "END"))
                        continue_conv = False

            except asyncio.TimeoutError:
                timeout = get_tip(lang, "TIMEOUT")
                await conv.send_message(timeout)

    except AlreadyInConversationError:
        await client.send_message(chat_id, get_tip(lang, "TIPS"))


@client.on(events.NewMessage)
async def media(event):
    lang = await user_lang(event.chat_id)

    if event.chat_id not in ADMIN_ID:
        if lang == LANG[0]:
            await event.respond(fr_msg)
            return 

        await event.respond(en_msg)

    else:
        if event.file or event.contact:
            await event.reply(get_tip(lang, "FILE"), parse_mode="md")
            new_logger(event.chat_id).debug("FILE")
        return


@client.on(events.NewMessage(pattern="/addAdmin"))
async def admin(event):
    chat_id = event.chat_id
    loop.create_task(admin_conv(chat_id, func="add"))
    raise events.StopPropagation


@client.on(events.NewMessage(pattern="/delAdmin"))
async def admin(event):
    chat_id = event.chat_id
    loop.create_task(admin_conv(chat_id, func="del"))
    raise events.StopPropagation


async def admin_conv(chat_id, func):

    if chat_id not in ADMIN_ID:
        return

    lang = await user_lang(chat_id)

    try:
        async with client.conversation(chat_id, timeout=120) as conv:
            await conv.send_message(f"Quel est le ID de l'utilisateur à ajouter?", parse_mode='md')

            try:
                continue_conv = True

                while continue_conv:
                    response = conv.get_response()
                    response = await response

                    if response.raw_text != "/end":
                        if func == "add":
                            try:
                                ADMIN_ID.append(response.raw_text)
                                await conv.send_message(f"Nouvel utilisateur ajouté.\n\nLa nouvelle liste est:\n{ADMIN_ID}")
                            except Exception as e:
                                await conv.send_message(e)
                        
                        else:
                            try:
                                if response.raw_text in ADMIN_ID:
                                    ADMIN_ID.remove(response.raw_text)
                                    await conv.send_message(f"L'utilisateur à bien été supprimé.\n\nLa nouvelle liste est:\n{ADMIN_ID}")
                                else:
                                    await conv.send_message("Cet utilisateur n'existe pas dans la liste.")
                            except Exception as e:
                                await conv.send_message(e)

                    else:
                        await conv.send_message("La liste des UTILISATEURS à bien été mis à jour.")
                        continue_conv = False

            except asyncio.TimeoutError:
                timeout = get_tip(lang, "TIMEOUT")
                await conv.send_message(timeout)


    except AlreadyInConversationError:
        await client.send_message(chat_id, get_tip(lang, "TIPS"))



def sig_handler():
    asyncio.run_coroutine_threadsafe(shutdown(client), asyncio.get_event_loop())


def run():
    client.start()
    print("Bot demarré avec succès..\n")
    asyncio.get_event_loop().add_signal_handler(signal.SIGABRT, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, sig_handler)
    client.run_until_disconnected()
