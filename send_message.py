import asyncio
from claquirou.users import UserBot
from telegram import Bot, ParseMode

TOKEN = "923335949:AAFguO4A5XsfqsMw_6JpqyVtGsN2pd6ZHm0"
bot = Bot(token=TOKEN)

async def inform_all_user():

    database = UserBot()
    get_user = await database.select_data
    z = 0

    for i in get_user:
        message = f"Bonsoir {i[1]}.\nLe bot n'est plus développée ni maintenue depuis un certain moment et ne le sera plus. Ce qui provoque déjà des erreurs etc... A bientôt"

        try:
            bot.send_message(i[0], message, parse_mode=ParseMode.MARKDOWN)
            print(f"Message envoyé au {i[0]}")
            z+= 1
        except Exception as e:
            print(e)

    print(f"Message envoyé à {z} utilisateurs")

loop = asyncio.get_event_loop()
loop.run_until_complete(inform_all_user())