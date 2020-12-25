import signal
import time
import asyncio

from telethon import Button, events
from telethon.errors import AlreadyInConversationError

from claquirou.admin import client, typing_action, get_user_id, user_lang, new_logger, get_tip, new_user
from claquirou.image import send_images
from claquirou.search import Search, Weather
from worker.download import send_files, shutdown

LANG = ["FR", "EN"]


@client.on(events.NewMessage(pattern="/start"))
async def option(event):
    keyboard = [
        [Button.inline("French 🇫🇷", b"10"),
         Button.inline("English 🇺🇸", b"20")],
    ]

    await client.send_message(event.chat_id, "Select language", buttons=keyboard)

    raise events.StopPropagation


@client.on(events.CallbackQuery)
async def button(event):
    user = event.chat
    all_users = await get_user_id()

    if event.data == b"10":
        await event.delete()

        now = time.strftime("%H", time.gmtime())
        greeting = "Bonjour" if 4 < int(now) < 18 else "Bonsoir"

        if user.id not in all_users:
            start_msg = get_tip("FR", "START")
            message = f"{greeting} {user.first_name}.\n{start_msg}"
            await event.respond(message)
        else:
            other = get_tip("FR", "OTHER")
            await event.respond(f"{greeting} {user.first_name}.\n{other}")

        await new_user(user.id, user.first_name, user.last_name, LANG[0])

    elif event.data == b"20":
        await event.delete()

        if user.id not in all_users:
            start_msg = get_tip("EN", "START")
            message = f"Hello {user.first_name}.\n{start_msg}"

            await event.respond(message)

        else:
            other = get_tip("EN", "OTHER")
            await event.respond(f"Hello {user.first_name}.\n{other}")

        await new_user(user.id, user.first_name, user.last_name, LANG[1])


@client.on(events.NewMessage(pattern="/help"))
async def helps(event):
    chat_id = event.chat_id

    await typing_action(chat_id)
    if await user_lang(chat_id) == LANG[0]:
        with open("claquirou/fr/help.txt", "r") as f:
            data = f.read()
    else:
        with open("claquirou/en/help.txt", "r") as f:
            data = f.read()

    await event.respond(data)
    new_logger(chat_id).debug("HELP")
    raise events.StopPropagation


loop = asyncio.get_event_loop()


@client.on(events.NewMessage(pattern="/options"))
async def option(event):
    chat_id = event.chat_id
    all_users = await get_user_id()

    if chat_id in all_users:
        lang = await user_lang(chat_id)
        keyboard = [
            [Button.inline(get_tip(lang, "CHOICE1"), b"1"),
             Button.inline(get_tip(lang, "CHOICE2"), b"2")],

            [Button.inline(get_tip(lang, "CHOICE3"), b"3"),
             Button.inline(get_tip(lang, "CHOICE4"), b"4")],

            [Button.inline(get_tip(lang, "CHOICE5"), b"5")]
        ]

        loop.create_task(client.send_message(chat_id, get_tip(lang, "SELECT"), buttons=keyboard))
        raise events.StopPropagation

    await event.respond(
        "Avant de continuer appuyez sur **/start** pour choisir une langue.\n\nBefore continuing press **/start** "
        "to choose a language.")


@client.on(events.CallbackQuery)
async def button(event):
    chat_id = event.chat_id
    lang = await user_lang(chat_id)

    if event.data == b"1" or event.data == b"01":
        await event.delete()
        search = Search(lang)
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "WEB"), search=search))

    elif event.data == b"2" or event.data == b"02":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "IMAGE"), search="image"))


    elif event.data == b"3" or event.data == b"03":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "AUDIO"), cmd="a"))


    elif event.data == b"4" or event.data == b"04":
        await event.delete()
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "VIDEO"), cmd="v"))


    elif event.data == b"5" or event.data == b"05":
        await event.delete()
        weather = Weather(lang)
        loop.create_task(user_conversation(chat_id=chat_id, tips=get_tip(lang, "METEO"), search=weather))

    raise events.StopPropagation


async def user_conversation(chat_id, tips, search=None, cmd=None):
    out = 600 if chat_id in [711322052, 1436379133] else 65
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
                                await typing_action(chat_id, period=7)
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
    all_users = await get_user_id()

    if event.chat_id in all_users:
        if event.file or event.contact:
            await event.reply(get_tip(lang, "FILE"), parse_mode="md")
            new_logger(event.chat_id).debug("FILE")
        return

    await event.respond(
        "Avant de continuer appuyez sur **/start** pour choisir une langue.\n\nBefore continuing press **/start** "
        "to choose a language.")


def sig_handler():
    asyncio.run_coroutine_threadsafe(shutdown(client), asyncio.get_event_loop())


def run():
    client.start()
    print("Bot demarré avec succès..")
    asyncio.get_event_loop().add_signal_handler(signal.SIGABRT, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, sig_handler)
    asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, sig_handler)
    client.run_until_disconnected()
