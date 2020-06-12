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
        # message = f"Bonsoir {i[1]}.\nNous tenions à vous informer que le bot sera temporairement indisponible jusqu'a 2:00 GMT en raison d’activités de maintenance...\nBonne soirée."

        message = f"Bonsoir {i[1]}.\nNous tenons à vous informer que le bot est à nouveau disponible suite à des mises à jour.\nDe nouvelles fonctionnalités sont disponible tel que les téléchargements simultanés d'audios, videos ou des playlists.\nVous pouvez également exécuter plusieurs tâches au même moment, par exemple: *Lancer des téléchargements et en même temps faire des recherches.*\n\nUne nouvelle langue 🇺🇸 sera disponible dans les jours à venir...Vos avis seront les bienvenus *@herve1774*"

        try:
            bot.send_message(i[0], message, parse_mode=ParseMode.MARKDOWN)
            print(f"Message envoyé au {i[0]}")
            z+= 1
        except Exception as e:
            print(e)


    print(f"Message envoyé à {z} utilisateurs")

loop = asyncio.get_event_loop()
loop.run_until_complete(inform_all_user())