import youtube_dl


url = "https://instagram.com/jonathan_agbon/live/17896554928541260?igshid=q4rzshbq7pdq"

ydl_opts = {}


with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
