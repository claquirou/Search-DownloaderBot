import asyncio

from telethon import Button, events

from claquirou.admin import new_user, client
import en.bot as Bot


loop = asyncio.get_event_loop()

@client.on(events.NewMessage(pattern="/start"))
async def option(event):
    user = event.chat
    chat_id = event.chat_id
    await new_user(chat_id, user.first_name, user.last_name)

    keyboard = [
        [Button.inline("French🇫🇷", b"1"),
         Button.inline("English🇺🇸", b"2")],
    ]

    await client.send_message(chat_id, "Language", buttons=keyboard)

    raise events.StopPropagation

@client.on(events.CallbackQuery)
async def button(event):
    chat_id = event.chat_id

    if event.data == b"1":
        await event.delete()


    elif event.data == b"2":
        await event.delete()




if __name__ == "__main__":
    Bot.run()
