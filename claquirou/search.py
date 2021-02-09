import requests
from bs4 import BeautifulSoup


class Search:
    def __init__(self, lang):
        self.lang = lang

    def _setup_requests(self, query, head=False):
        http_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/44.0.2403.157 Safari/537.36",
            "Accept-Charset": "fr-FR,en;q=0.5",
            "Accept": "gzip, deflate",
            "Accept-Encoding": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "Accept-Language": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        search = query.replace(" ", "+")

        if self.lang == "FR":
            url = f"https://www.google.com/search?lr=lang_fr&ie=UTF-8&q={search}"
        else:
            url = f"https://www.google.com/search?hl=en&q={search}"
        if head:
            response = requests.get(url, headers=http_headers)
        else:
            response = requests.get(url, {"User-Agent": http_headers})

        return BeautifulSoup(response.text, "html.parser")

    def get_data(self, query, tag, attrs):
        soup = self._setup_requests(query, head=True)
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

        finally:
            page = soup.find_all(tag, attrs)
            page = [i.text for i in page]
            return "\n".join(page)

    def results(self, query):
        description = self.get_data(query=query, tag="div", attrs={"class": "LMRCfc"})
        synonym = self.get_data(query=query, tag="ol", attrs={"class": "eQJLDd"})
        other_synonym = self.get_data(query=query, tag="div", attrs={"class": "di3YZe"})
        actor = self.get_data(query=query, tag="div", attrs={"class": "FozYP"})

        return description or synonym or other_synonym or actor

    def other_result(self, query):
        soup = self._setup_requests(query)

        page = soup.find_all('div', attrs={'class': 'ZINbbc'})
        for r in page:
            try:
                description = r.find('div', attrs={'class': 's3v9rd'}).get_text()
                if description:
                    return description
            except:
                continue


if __name__ == '__main__':
    a = Search("EN")
