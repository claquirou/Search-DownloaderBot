from __future__ import unicode_literals

import os

import youtube_dl


FOLDER = os.path.dirname(__file__)


class YoutubeDownloader:
    def __init__(self, url):
        self.url = url

    def extract_data(self, file_type, download):
        ytdl = self.options(file_type)
    
        with youtube_dl.YoutubeDL(ytdl) as ydl:
            data = ydl.extract_info(self.url, download=download)
                
        return data

    def options(self, file_type):

        if file_type == "audio":
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "noplaylist": True,
                "outtmpl": "audio.%(ext)s",
                "quiet": True
            }

        elif file_type == "video":
            ydl_opts = {
                "format": "best",
                "noplaylist": True,
                # "outtmpl": "%(title)s.%(ext)s",
                "quiet": True
                }
        else:
            ydl_opts = "Type du fichier non reconnue.\nLes types disponible sont: 'audio' et 'video'"

        return ydl_opts

    def audio(self):
        data = self.extract_data(file_type="audio", download=True) 
        content = []

        title = data.get("title")
        title_ext = f"audio.mp3"
        path = os.path.join(os.path.dirname(FOLDER), title_ext)
        
        content.extend([path, title])
        return content

    def video(self):
        data = self.extract_data(file_type="video", download=False)
        content = []
        title = data.get("title")
        formats = data.get("formats")
        
        try:
            if "instagram" in self.url:
                url = data.get("url")
            
            elif "tiktok" in self.url:
                entrie = data.get("entries")
                for i in entrie:
                    formats = i.get("formats")
                    for j in formats:
                        url = j.get("url")
        
        except:
            return

        finally:
            content.extend([url, title])
            return content

if __name__ == "__main__":
    test = YoutubeDownloader("https://www.youtube.com/watch?v=iHaeZzw9Hz0")
    print(test.video())
