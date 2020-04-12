import requests
from bs4 import BeautifulSoup


class Search:
    def __init__(self):
        pass
    
    def setup_requests(self, url):     
        http_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36",
            "Accept-Charset": "fr-FR,en;q=0.5",
            "Accept": "gzip, deflate",
            "Accept-Encoding": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "Accept-Language": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }    

        response = requests.get(url, headers=http_headers)
        soup = BeautifulSoup(response.text, "html.parser", )
        return soup

    def _get_search(self, query, tag, attrs={}):
        url = f"https://www.google.com/search?lr=lang_fr&ie=UTF-8&q={query.replace(' ', '+')}"
        soup = self.setup_requests(url)
        page = soup.find(tag, attrs)
        
        try:
            page = page.find_all("span")
            page = [string.text for string in page]
            return "\n".join(page)
        
        except AttributeError:
            # other synonym
            page = soup.find_all(tag, attrs)
            page = [i.text.replace(".", "\n") for i in page]
            return "\n".join(page)

        else:
            page = soup.find_all(tag, attrs)
            page = [i.text for i in page]
            return "\n".join(page)
        

    def results(self, query):
        description = self._get_search(query, "div", attrs={"class": "SALvLe"})
        synonym = self._get_search(query, "ol", attrs={"class": "eQJLDd"})
        other_synonym = self._get_search(query, "div", attrs={"class": "di3YZe"})
        actor = self._get_search(query, "div", attrs={"class": "wfg6Pb"})
        medecine = self._get_search(query, "div", attrs={"class": "wQu7gc"})
        
        return description or synonym or other_synonym or actor or medecine

class Weather(Search):
    def __init__(self):
        super().__init__()
    
    def get_info(self, query):
        url = f"https://www.google.com/search?lr=lang_fr&ie=UTF-8&q=meteo+{query}"
        soup = self.setup_requests(url)

        data = {
            "region": soup.find(id='wob_loc').text,
            "temperature_now": soup.find(id='wob_tm').text,
            "date": soup.find(id='wob_dts').text,
            "weather_now": soup.find(id='wob_dc').text,
            "precipitation": soup.find(id='wob_pp').text,
            "humidity": soup.find(id='wob_hm').text,
            "wind": soup.find(id='wob_ws').text
            }

        return data

    def results(self, query):
        try:
            data = self.get_info(query)
            result = f"""
Localisation: {data.get("region")},
Date: {data.get("date")},
Température: {data.get("temperature_now")}°C,
Description: {data.get("weather_now")},
Précipitation: {data.get("precipitation")},
Humidité: {data.get("humidity")},
Vent: {data.get("wind")},
"""
        
            return result
        
        except AttributeError:
            return "Ville incorrecte! Assurez d'avoir bien saisie le nom de la ville"


if __name__ == "__main__":
    a = Search()
    print(a.results("Port 5454541Boulet"))