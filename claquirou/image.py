from selenium import webdriver
import random
import os

chrome_options = webdriver.ChromeOptions()
chrome_options.binary_location = os.environ["GOOGLE_CHROME_BIN"]
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")


def send_images(query):
    query = query.split()
    if "".join(query).isdigit():
        return "Vous avez uniquement écrit un/des chiffre(s)\nFaites des recherches précises svp..."

    img_number = query.pop(-1)

    try:
        number = int(img_number)
        if number <= 0:
            return "Le nombre de l'image doit être supérieur à 0."
        elif number > 15:
            return "Le nombre de l'image doit être inférieur ou égale à 15.\nVeuillez réessayer svp."
        else:
            search = "+".join(query)
            url = f"https://www.google.co.in/search?q={search}&source=lnms&tbm=isch"
            images = initialise_requests(url, number)
            return images
    
    except ValueError:
        return "Format incorrect !\nVous avez fait une erreur, écrivez le nom de l'image suivi du nombre d'image que vous voulez."
    

# Scrap image
def initialise_requests(url, number):
    browser = webdriver.Chrome(executable_path=os.environ["CHROMEDRIVER_PATH"], chrome_options=chrome_options)
    # browser = webdriver.Chrome("/home/claquirou/Bureau/MyBot/chromedriver")
    browser.get(url)
    extensions = {"jpg", "jpeg", "png", "gif"}

    for _ in range(25):
        browser.execute_script("window.scrollBy(0,200)")
        
    html = browser.page_source.split('["')
    images = [i.split('"')[0] for i in html if i.startswith('http') and i.split('"')[0].split('.')[-1] in extensions]
    random.shuffle(images)

    images.append(number)
    browser.close()
    
    return images

