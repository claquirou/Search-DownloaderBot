import os
import random

from selenium import webdriver

from claquirou.admin import get_tip

chrome_options = webdriver.ChromeOptions()
chrome_options.binary_location = os.environ["GOOGLE_CHROME_BIN"]
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")


def send_images(query, lang):
    query = query.split()
    if "".join(query).isdigit():
        return get_tip(lang, "IMG1")

    img_number = query.pop(-1)

    try:
        number = int(img_number)
        if number <= 0:
            return get_tip(lang, "IMG2")
        elif number > 15:
            return get_tip(lang, "IMG3")
        else:
            search = "+".join(query)
            url = f"https://www.google.com/search?q={search}&source=lnms&tbm=isch"
            return initialise_requests(url, number)

    except ValueError:
        return get_tip(lang, "IMG4")
    

# Scrap image
def initialise_requests(url, number):
    browser = webdriver.Chrome(executable_path=os.environ["CHROMEDRIVER_PATH"], chrome_options=chrome_options)
    # browser = webdriver.Chrome(".test/chromedriver")
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
