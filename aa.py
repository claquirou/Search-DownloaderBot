import asyncio
from claquirou.users import UserBot
from telegram import Bot

bot = Bot("923335949:AAFIYfsrV-6h_K52giygRPh650GUfaZdRnU")

async def inform_all_user():

    database = UserBot()
    get_user = await database.select_data

    # for i in get_user:
        # message = f"Bonsoir {i[1]}.\nNous tenions à vous informer que le bot est temporairement indisponible jusqu'au 06 Avril en raison d’activités de maintenance ...\nMerci pour votre compréhension."

        # message = f"Nous avons corrigé un bug qui empêchait les recherches d'images. Vous pouvez à nouveau faire vos recherches..."

        # bot.send_message(i[0], message)


# asyncio.get_event_loop().run_until_complete(inform_all_user())