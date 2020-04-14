from selenium import webdriver
import random

GOOGLE_CHROME_PATH = '/app/.apt/usr/bin/google_chrome'
CHROMEDRIVER_PATH = '/app/.chromedriver/bin/chromedriver'

chrome_options = webdriver.ChromeOptions()
chrome_options.binary_location = GOOGLE_CHROME_PATH
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")


def send_images(query):
    query = query.split()
    print(query)
    img_number = query.pop(-1)
    print(img_number)

    if "".join(query).isdigit():
        return "Faites des recherches précises svp..."

    try:
        number = int(img_number)
        print(type(number))
        if number > 15:
            return "Le nombre de l'image doit être inférieur ou égale à 15.\nVeuillez réessayer svp."
        else:
            search = "+".join(query)
            url = f"https://www.google.co.in/search?q={search}&source=lnms&tbm=isch"
            images = initialise_requests(url, number)
            return images
    
    except:
        return "Format incorrect !\nVous avez fait une erreur, le nombre de l'image doit être un nombre entier."
    

# Scrap image
def initialise_requests(url, number):
    browser = webdriver.Chrome(execution_path=CHROMEDRIVER_PATH, chrome_options=chrome_options)
    # browser = webdriver.Chrome("/home/claquirou/Bureau/AllTest/chromedriver")
    webdriver.Chrome()
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

