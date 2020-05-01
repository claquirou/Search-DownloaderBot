import asyncio
from claquirou.users import UserBot
from telegram import Bot

bot = Bot("923335949:AAFIYfsrV-6h_K52giygRPh650GUfaZdRnU")

async def inform_all_user():

    database = UserBot()
    get_user = await database.select_data
    z = 0

    for i in get_user:
        # message = f"Bonsoir {i[1]}.\nNous tenions à vous informer que le bot sera temporairement indisponible jusqu'a 2:00 GMT en raison d’activités de maintenance...\nBonne soirée."

        message = f"Bonjour {i[1]}.\nNous tenions à vous informer que le bot est à nouveau disponible.\nPetite astuce: Pour afficher les options appuyez sur /options et pour mettre fin à une conversation pour faire d'autre choix appuyez sur /end .Pour avoir de l'aide, appuyez sur /help ."
        try:
            bot.send_message(i[0], message)
            print(f"Message envoyé au {i[0]}")
            z+= 1
        except Exception as e:
            print(e)


    print(f"Message envoyé à {z} utilisateurs")

asyncio.get_event_loop().run_until_complete(inform_all_user())