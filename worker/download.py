import asyncio
import functools
import inspect
import mimetypes
import os
import re
from datetime import time, timedelta
from urllib.error import HTTPError
from urllib.parse import urlparse, urlunparse

import aiofiles
import youtube_dl
from aiogram import Bot
from urlextract import URLExtract
from telethon.errors import AuthKeyDuplicatedError
from telethon.tl.types import (DocumentAttributeAudio,
                               DocumentAttributeFilename,
                               DocumentAttributeVideo)

import worker.av_source as av_source
import worker.av_utils as av_utils
import worker.cut_time as cut_time
import worker.fast_telethon as fast_telethon
import worker.tgaction as tgaction
import worker.thumb as thumb

TOKEN = os.environ["TOKEN"]
# TOKEN = "751185862:AAHQ21D01OUELDvEzbhDs-dEkTpy1Nl2OFI"
_bot = Bot(TOKEN)

url_extractor = URLExtract()

TG_MAX_FILE_SIZE = 1500 * 1024 * 1024
TG_MAX_PARALLEL_CONNECTIONS = 30
TG_CONNECTIONS_COUNT = 0
MAX_STORAGE_SIZE = 1500 * 1024 * 1024
STORAGE_SIZE = MAX_STORAGE_SIZE

def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


async def extract_url_info(ydl, url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None,
                            functools.partial(ydl.extract_info,
                            download=False,
                            force_generic_extractor=ydl.params.get(
                            'force_generic_extractor', False)),
                            url)


def normalize_url_path(url):
    parsed = list(urlparse(url))
    parsed[2] = re.sub("/{2,}", "/", parsed[2])

    return urlunparse(parsed)


is_ytb_link_re = re.compile(r'^((?:https?:)?\/\/)?((?:www|m|music)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$')
get_ytb_id_re = re.compile(r'.*(youtu.be\/|v\/|embed\/|watch\?|youtube.com\/user\/[^#]*#([^\/]*?\/)*)\??v?=?([^#\&\?]*).*')

def youtube_to_invidio(url, audio=False):
    u = None
    if is_ytb_link_re.search(url):
        ytb_id_match = get_ytb_id_re.search(url)
        if ytb_id_match:
            ytb_id = ytb_id_match.groups()[-1]
            u = "https://invidio.us/watch?v=" + ytb_id + "&quality=dash"
            if audio:
                u += '&listen=1'
    return u


async def send_files(client, chat_id, message, cmd, log, msg_id=54540):
    global STORAGE_SIZE

    log.info(f"URL: {message}")

    urls = url_extractor.find_urls(message)
    if len(urls) == 0:
        await client.send_message(chat_id, "L'URL de la vidéo est incorrect")

    playlist_start = None
    playlist_end = None

    # check cmd and choose video format    
    cut_time_start = cut_time_end = None

    if cmd == 'a':
        preferred_formats = [audio_format]
        action = "upload_audio"
    else:
        preferred_formats = [vid_hd_format, vid_nhd_format]
        action = "upload_video"
    
    async with tgaction.TGAction(_bot, chat_id, action):
        urls = set(urls)
        for iu, u in enumerate(urls):
            vinfo = None
            params = {'noplaylist': True,
                      'youtube_include_dash_manifest': False,
                      'quiet': True,
                      'no_color': True,
                      'nocheckcertificate': True}
            if playlist_start != None and playlist_end != None:
                if playlist_start == 0 and playlist_end == 0:
                    params['playliststart'] = 1
                    params['playlistend'] = 10
                else:
                    params['playliststart'] = playlist_start
                    params['playlistend'] = playlist_end
            else:
                params['playlist_items'] = '1'

            ydl = youtube_dl.YoutubeDL(params=params)
            recover_playlist_index = None  # to save last playlist position if finding format failed
            for ip, pref_format in enumerate(preferred_formats):
                try:
                    params['format'] = pref_format
                    if recover_playlist_index is not None and 'playliststart' in params:
                        params['playliststart'] += recover_playlist_index
                    ydl.params = params
                    if vinfo is None:
                        for _ in range(2):
                            try:
                                vinfo = await extract_url_info(ydl, u)
                                if vinfo.get('age_limit') == 18 and is_ytb_link_re.search(vinfo.get('webpage_url', '')):
                                    raise youtube_dl.DownloadError('youtube age limit')
                            except youtube_dl.DownloadError as e:
                                # try to use invidio.us youtube frontend to bypass 429 block
                                if (e.exc_info is not None and e.exc_info[0] is HTTPError and e.exc_info[1].file.code == 429) or \
                                        'video available in your country' in str(e) or \
                                        'youtube age limit' == str(e):
                                    invid_url = youtube_to_invidio(u, cmd == 'a')
                                    if invid_url:
                                        u = invid_url
                                        ydl.params['force_generic_extractor'] = True
                                        continue
                                    raise
                                else:
                                    raise

                            break

                        log.debug('Extraction de la vidéo en cours...')
                    else:
                        if '_type' in vinfo and vinfo['_type'] == 'playlist':
                            for i, e in enumerate(vinfo['entries']):
                                e['requested_formats'] = None
                                vinfo['entries'][i] = ydl.process_video_result(e, download=False)
                        else:
                            vinfo['requested_formats'] = None
                            vinfo = ydl.process_video_result(vinfo, download=False)
                        log.debug('Les informations de la vidéo retraitées avec un nouveau format')
                except Exception as e:
                    if "Please log in or sign up to view this video" in str(e):
                        if 'vk.com' in u:
                            params['username'] = os.environ['VIDEO_ACCOUNT_USERNAME']
                            params['password'] = os.environ['VIDEO_ACCOUNT_PASSWORD']
                            ydl = youtube_dl.YoutubeDL(params=params)
                            try:
                                vinfo = await extract_url_info(ydl, u)
                            except Exception as e:
                                log.error(e)
                                await client.send_message(chat_id, str(e))
                                continue
                        else:
                            log.error(e)
                            await client.send_message(chat_id, str(e))
                            continue
                    elif 'are video-only' in str(e):
                        params['format'] = 'bestvideo[ext=mp4]'
                        ydl = youtube_dl.YoutubeDL(params=params)
                        try:
                            vinfo = await extract_url_info(ydl, u)
                        except Exception as e:
                            log.error(e)
                            await client.send_message(chat_id, str(e))
                            continue
                    else:
                        if iu < len(urls) - 1:
                            log.error(e)
                            await client.send_message(chat_id, str(e))
                            break

                        raise

                entries = None
                if '_type' in vinfo and vinfo['_type'] == 'playlist':
                    entries = vinfo['entries']
                else:
                    entries = [vinfo]

                for ie, entry in enumerate(entries):
                    formats = entry.get('requested_formats')
                    file_size = None
                    chosen_format = None
                    ffmpeg_av = None
                    http_headers = None
                    if 'http_headers' not in entry:
                        if len(formats) > 0 and 'http_headers' in formats[0]:
                            http_headers = formats[0]['http_headers']
                    else:
                        http_headers = entry['http_headers']
                    http_headers['Referer'] = u

                    _title = entry.get('title', '')
                    if _title == '':
                        entry['title'] = str(msg_id)


                    _cut_time = (cut_time_start, cut_time_end) if cut_time_start else None
                    try:
                        if formats is not None:
                            for i, f in enumerate(formats):
                                if f['protocol'] in ['rtsp', 'rtmp', 'rtmpe', 'mms', 'f4m', 'ism', 'http_dash_segments']:
                                    continue
                                if 'm3u8' in f['protocol']:
                                    file_size = await av_utils.m3u8_video_size(f['url'], http_headers)
                                else:
                                    if 'filesize' in f and f['filesize'] != 0 and f['filesize'] is not None and f['filesize'] != 'none':
                                        file_size = f['filesize']
                                    else:
                                        try:
                                            direct_url = f['url']
                                            if 'invidio.us' in direct_url:
                                                direct_url = normalize_url_path(direct_url)
                                            file_size = await av_utils.media_size(direct_url, http_headers=http_headers)
                                        except Exception as e:
                                            if i < len(formats) - 1 and '404 Not Found' in str(e):
                                                break
                                            else:
                                                raise

                                # Dash video
                                if f['protocol'] == 'https' and \
                                        (True if ('acodec' in f and (f['acodec'] == 'none' or f['acodec'] == None)) else False):
                                    vformat = f
                                    mformat = None
                                    vsize = 0

                                    direct_url = vformat['url']
                                    if 'invidio.us' in direct_url:
                                        vformat['url'] = normalize_url_path(direct_url)

                                    if 'filesize' in vformat and vformat['filesize'] != 0 and vformat['filesize'] is not None and vformat['filesize'] != 'none':
                                        vsize = vformat['filesize']
                                    else:
                                        vsize = await av_utils.media_size(vformat['url'], http_headers=http_headers)
                                    msize = 0
                                    # if there is one more format than
                                    # it's likely an url to audio
                                    if len(formats) > i + 1:
                                        mformat = formats[i + 1]

                                        direct_url = mformat['url']
                                        if 'invidio.us' in direct_url:
                                            mformat['url'] = normalize_url_path(direct_url)

                                        if 'filesize' in mformat and mformat['filesize'] != 0 and mformat[
                                            'filesize'] is not None and mformat['filesize'] != 'none':
                                            msize = mformat['filesize']
                                        else:
                                            msize = await av_utils.media_size(mformat['url'], http_headers=http_headers)
                                    # we can't precisely predict media size so make it large for prevent cutting
                                    file_size = vsize + msize + 10 * 1024 * 1024
                                    if file_size < TG_MAX_FILE_SIZE or cut_time_start is not None:
                                        file_name = None
                                        if not cut_time_start and STORAGE_SIZE > file_size > 0:
                                            STORAGE_SIZE -= file_size
                                            _ext = 'mp4' if cmd != 'a' else 'mp3'
                                            file_name = entry['title'] + '.' + _ext
                                        ffmpeg_av = await av_source.FFMpegAV.create(vformat,
                                                                                    mformat,
                                                                                    headers=http_headers,
                                                                                    cut_time_range=_cut_time,
                                                                                    file_name=file_name)
                                        chosen_format = f
                                    break
                                # m3u8
                                if ('m3u8' in f['protocol'] and
                                        (file_size <= TG_MAX_FILE_SIZE or cut_time_start is not None)):
                                    chosen_format = f
                                    acodec = f.get('acodec')
                                    if acodec is None or acodec == 'none':
                                        if len(formats) > i + 1:
                                            mformat = formats[i + 1]
                                            if 'filesize' in mformat and mformat['filesize'] != 0 and mformat[
                                                'filesize'] is not None and mformat['filesize'] != 'none':
                                                msize = mformat['filesize']
                                            else:
                                                msize = await av_utils.media_size(mformat['url'], http_headers=http_headers)
                                            msize += 10 * 1024 * 1024
                                            if (msize + file_size) > TG_MAX_FILE_SIZE:
                                                mformat = None
                                            else:
                                                file_size += msize

                                    file_name = None
                                    if not cut_time_start and STORAGE_SIZE > file_size > 0:
                                        STORAGE_SIZE -= file_size
                                        _ext = 'mp4' if cmd != 'a' else 'mp3'
                                        file_name = entry['title'] + '.' + _ext
                                    ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                aformat=mformat,
                                                                                audio_only=True if cmd == 'a' else False,
                                                                                headers=http_headers,
                                                                                cut_time_range=_cut_time,
                                                                                file_name=file_name)
                                    break
                                # regular video stream
                                if (0 < file_size <= TG_MAX_FILE_SIZE) or cut_time_start is not None:
                                    chosen_format = f

                                    direct_url = chosen_format['url']
                                    if 'invidio.us' in direct_url:
                                        chosen_format['url'] = normalize_url_path(direct_url)

                                    if cmd == 'a' and not (chosen_format['ext'] == 'mp3'):
                                        ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                    audio_only=True,
                                                                                    headers=http_headers,
                                                                                    cut_time_range=_cut_time)
                                    break

                        else:
                            if entry['protocol'] in ['rtsp', 'rtmp', 'rtmpe', 'mms', 'f4m', 'ism', 'http_dash_segments']:
                                recover_playlist_index = ie
                                break
                            if 'm3u8' in entry['protocol']:
                                if cut_time_start is None and entry.get('is_live', False) is False and cmd != 'a':
                                    file_size = await av_utils.m3u8_video_size(entry['url'], http_headers=http_headers)
                                else:
                                    # we don't know real size
                                    file_size = 0
                            else:
                                if 'filesize' in entry and entry['filesize'] != 0 and entry['filesize'] is not None and entry['filesize'] != 'none':
                                    file_size = entry['filesize']
                                else:
                                    direct_url = entry['url']
                                    if 'invidio.us' in direct_url:
                                        entry['url'] = normalize_url_path(direct_url)
                                    file_size = await av_utils.media_size(direct_url, http_headers=http_headers)
                            if ('m3u8' in entry['protocol'] and
                                    (file_size <= TG_MAX_FILE_SIZE or cut_time_start is not None)):
                                chosen_format = entry
                                if entry.get('is_live') and not _cut_time:
                                    cut_time_start, cut_time_end = (time(hour=0, minute=0, second=0),
                                                                    time(hour=1, minute=0, second=0))
                                    _cut_time = (cut_time_start, cut_time_end)
                                file_name = None
                                if not cut_time_start and STORAGE_SIZE > file_size > 0:
                                    STORAGE_SIZE -= file_size
                                    _ext = 'mp4' if cmd != 'a' else 'mp3'
                                    file_name = entry['title'] + '.' + _ext
                                ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                            audio_only=True if cmd == 'a' else False,
                                                                            headers=http_headers,
                                                                            cut_time_range=_cut_time,
                                                                            file_name=file_name)
                            elif (file_size <= TG_MAX_FILE_SIZE) or cut_time_start is not None:
                                chosen_format = entry
                                direct_url = chosen_format['url']
                                if 'invidio.us' in direct_url:
                                    chosen_format['url'] = normalize_url_path(direct_url)
                                if cmd == 'a' and not (chosen_format['ext'] == 'mp3'):
                                    ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                audio_only=True,
                                                                                headers=http_headers,
                                                                                cut_time_range=_cut_time)

                        if chosen_format is None and ffmpeg_av is None:
                            if len(preferred_formats) - 1 == ip:
                                if file_size > TG_MAX_FILE_SIZE:
                                    log.info(f"Fichier trop volumineux {file_size}")

                                    await client.send_message(chat_id, f"ERREUR: Taille de fichier multimédia trop grande **{sizeof_fmt(file_size)}**\nTelegram autorise les fichiers moins de **1.5GB**")
                                else:
                                    log.info('Echec de la recherche du format de support approprié')
                                    await client.send_message(chat_id, "ERREUR: Echec de la recherche du format de support approprié")
                                return
                           
                            recover_playlist_index = ie
                            break
                        if cmd == 'a' and file_size != 0 and (ffmpeg_av is None or ffmpeg_av.file_name is None):
                            # we don't know real size due to converting formats
                            # so increase it in case of real size is less large then estimated
                            file_size += 10 * 1024 * 1024 # 10MB

                        await client.send_message(chat_id, "Votre fichier est en cours de telechargement. Patientez quelque seconde.")
                        log.debug('Fichier en cours de téléchargement...')

                        width = height = duration = None
                        format_name = ''
                        if cmd == 'a':
                            if ('duration' not in entry and 'duration' not in chosen_format):
                                # info = await av_utils.av_info(chosen_format['url'],
                                #                               use_m3u8=('m3u8' in chosen_format['protocol']))
                                info = await av_utils.av_info(chosen_format['url'], http_headers=http_headers)
                                duration = int(float(info['format'].get('duration', 0)))
                            else:
                                duration = int(entry['duration']) if 'duration' not in entry else int(entry['duration'])

                        elif ('duration' not in entry and 'duration' not in chosen_format) or \
                                ('width' not in chosen_format) or ('height' not in chosen_format):
                            # info =  await av_utils.av_info(chosen_format['url'],
                            #                                use_m3u8=('m3u8' in chosen_format['protocol']))
                            info = await av_utils.av_info(chosen_format['url'], http_headers=http_headers)
                            try:
                                streams = info['streams']
                                if len(streams) > 0:
                                    width = streams[0]['width']
                                    height = streams[0]['height']
                                else:
                                    cmd = 'a'
                                duration = int(float(info['format'].get('duration', 0)))
                                format_name = info['format'].get('format_name', '').split(',')[0]
                            except KeyError:
                                width = 0
                                height = 0
                                duration = 0
                                format_name = ''
                        else:
                            width, height, duration = chosen_format['width'], chosen_format['height'], \
                                                      int(entry['duration']) if 'duration' not in entry else int(
                                                          entry['duration'])

                        if 'mp4 - unknown' in chosen_format.get('format', '') and chosen_format.get('ext', '') != 'mp4':
                            chosen_format['ext'] = 'mp4'
                        elif 'unknown' in chosen_format['ext']:
                            mime = await av_utils.media_mime(chosen_format['url'], http_headers=http_headers)
                            ext = mimetypes.guess_extension(mime)
                            if ext is None or ext == '':
                                if format_name is None:
                                    if len(preferred_formats) - 1 == ip:
                                        await client.send_message(chat_id, "ERROR: Failed find suitable media format",
                                                                )
                                    # await bot.send_message(chat_id, "ERROR: Failed find suitable video format", reply_to=msg_id)
                                    continue
                                else:
                                    chosen_format['ext'] = format_name
                            else:
                                ext = ext[1:]
                                media_type = mime.split('/')[0]
                                if media_type != 'audio' and media_type != 'video' and format_name != '':
                                    if format_name == 'mov':
                                        format_name = 'mp4'
                                    chosen_format['ext'] = format_name
                                else:
                                    chosen_format['ext'] = ext

                        # in case of video is live we don't know real duration
                        if cut_time_start is not None:
                            if not entry.get('is_live'):
                                if cut_time.time_to_seconds(cut_time_start) > duration:
                                    await client.send_message(chat_id,  f"ERROR: L'heure de début est plus longue que la durée du fichier {timedelta(seconds=duration)}")
                                    return
                                elif cut_time_end is not None and cut_time.time_to_seconds(cut_time_end) > duration:
                                    await client.send_message(chat_id, f"ERROR: L'heure de fin est plus longue que la durée du fichier {timedelta(seconds=duration)}")
                                    return
                                elif cut_time_end is None:
                                    duration = duration - cut_time.time_to_seconds(cut_time_start)
                                else:
                                    duration = cut_time.time_to_seconds(cut_time_end) - cut_time.time_to_seconds(cut_time_start)
                            else:
                                duration = cut_time.time_to_seconds(cut_time_end) - cut_time.time_to_seconds(
                                    cut_time_start)

                        if cut_time_start is not None and ffmpeg_av is None:
                            ext = chosen_format.get('ext')
                            ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                        headers=http_headers,
                                                                        cut_time_range=_cut_time,
                                                                        ext=ext,
                                                                        format_name=format_name if ext != 'mp4' and format_name != '' else '')
                        upload_file = ffmpeg_av if ffmpeg_av is not None else await av_source.URLav.create(
                            chosen_format['url'],
                            http_headers)

                        ext = (chosen_format['ext'] if ffmpeg_av is None or ffmpeg_av.format is None else ffmpeg_av.format)
                        file_name = entry['title'] + '.' + ext
                        if file_size == 0:
                            log.warning('file size is 0')

                        file_size = file_size if file_size != 0 and file_size < TG_MAX_FILE_SIZE else TG_MAX_FILE_SIZE

                        ffmpeg_cancel_task = None
                        if ffmpeg_av is not None:
                            ffmpeg_cancel_task = asyncio.get_event_loop().call_later(4000, ffmpeg_av.safe_close)
                        global TG_CONNECTIONS_COUNT
                        global TG_MAX_PARALLEL_CONNECTIONS
                        try:
                            if ffmpeg_av and ffmpeg_av.file_name:
                                await ffmpeg_av.stream.wait()
                                file_size_real = os.path.getsize(ffmpeg_av.file_name)
                                STORAGE_SIZE += file_size - file_size_real
                                file_size = file_size_real
                                local_file = aiofiles.open(ffmpeg_av.file_name, mode='rb')
                                upload_file = await local_file.__aenter__()
                            # uploading piped ffmpeg file is slow anyway
                            # TODO проверка на то что ffmpeg_av имееет file_name
                            if (file_size > 20*1024*1024 and TG_CONNECTIONS_COUNT < TG_MAX_PARALLEL_CONNECTIONS) and \
                                (isinstance(upload_file, av_source.URLav) or
                                 isinstance(upload_file, aiofiles.threadpool.binary.AsyncBufferedReader)):
                                try:
                                    connections = 2
                                    if TG_CONNECTIONS_COUNT < 12 and file_size > 100*1024*1024:
                                        connections = 4

                                    TG_CONNECTIONS_COUNT += connections
                                    file = await fast_telethon.upload_file(client,
                                                                           upload_file,
                                                                           file_size,
                                                                           file_name,
                                                                           max_connection=connections)
                                finally:
                                    TG_CONNECTIONS_COUNT -= connections
                            else:
                                file = await client.upload_file(upload_file,
                                                                file_name=file_name,
                                                                file_size=file_size,
                                                                http_headers=http_headers)
                        except AuthKeyDuplicatedError as e:
                            await client.send_message(chat_id, 'ERREUR INTERNE: réessayez')
                            log.fatal(e)
                            os.abort()
                        finally:
                            if ffmpeg_av and ffmpeg_av.file_name:
                                STORAGE_SIZE += file_size
                                if STORAGE_SIZE > MAX_STORAGE_SIZE:
                                    log.warning("Erreur logique, taille de stockage récupérée plus grande qu'initial")
                                    STORAGE_SIZE = MAX_STORAGE_SIZE
                                if isinstance(upload_file, aiofiles.threadpool.binary.AsyncBufferedReader):
                                    await local_file.__aexit__(exc_type=None, exc_val=None, exc_tb=None)
                                try:
                                    os.remove(ffmpeg_av.file_name)
                                except Exception as e:
                                    log.exception(e)

                            if ffmpeg_cancel_task is not None and not ffmpeg_cancel_task.cancelled():
                                ffmpeg_cancel_task.cancel()

                            if upload_file is not None:
                                if inspect.iscoroutinefunction(upload_file.close):
                                    await upload_file.close()
                                else:
                                    upload_file.close()

                        attributes = None
                        if cmd == 'a':
                            performer = entry['artist'] if ('artist' in entry) and \
                                                           (entry['artist'] is not None) else None
                            title = entry['alt_title'] if ('alt_title' in entry) and \
                                                          (entry['alt_title'] is not None) else entry['title']
                            attributes = DocumentAttributeAudio(duration, title=title, performer=performer)
                        elif ext == 'mp4':
                            supports_streaming = False if ffmpeg_av is not None and ffmpeg_av.file_name is None else True
                            attributes = DocumentAttributeVideo(duration,
                                                                width,
                                                                height,
                                                                supports_streaming=supports_streaming)
                        else:
                            attributes = DocumentAttributeFilename(file_name)
                        force_document = False
                        if ext != 'mp4' and cmd != 'a':
                            force_document = True
                        log.debug('Envoie du fichier.')
                        video_note = False if cmd == 'a' or force_document else True
                        voice_note = True if cmd == 'a' else False
                        attributes = ((attributes,) if not force_document else None)
                        caption = entry['title']
                        recover_playlist_index = None
                        _thumb = None
                        try:
                            _thumb = await thumb.get_thumbnail(entry)
                        except Exception as e:
                            log.warning(f"Echec de l'obtention de la miniature: {e}")

                        for i in range(10):
                            try:
                                await client.send_file(chat_id, file,
                                                       video_note=video_note,
                                                       voice_note=voice_note,
                                                       attributes=attributes,
                                                       caption=caption,
                                                       force_document=force_document,
                                                       supports_streaming=False if ffmpeg_av is not None else True,
                                                       thumb=_thumb)
                            except AuthKeyDuplicatedError as e:
                                await client.send_message(chat_id, 'ERREUR INTERNE: réessayez')
                                log.fatal(e)
                                os.abort()
                            except Exception as e:
                                log.exception(e)
                                await asyncio.sleep(1)
                                continue

                            break
                    except AuthKeyDuplicatedError as e:
                        await client.send_message(chat_id, 'ERREUR INTERNE: réessayez')
                        log.fatal(e)
                        os.abort()
                    except Exception as e:
                        if len(preferred_formats) - 1 <= ip:
                            # raise exception for notify user about error
                            raise
                        else:
                            log.warning(e)
                            recover_playlist_index = ie

                if recover_playlist_index is None:
                    break




vid_hd_format = '((best[ext=mp4][height<=720][height>360])[protocol^=http]/best[ext=mp4][height<=720][height>360]/  (bestvideo[ext=mp4][height<=720][height>360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=720][height>360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=720][height>360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio) /  (best[ext=mp4][height<=360])[protocol^=http]/best[ext=mp4][height<=360]/  (bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/   best[ext=mp4]   /bestvideo[ext=mp4]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/best)[protocol!=http_dash_segments][vcodec !^=? av01]'
vid_nhd_format = '((best[ext=mp4][height<=360])[protocol^=http]/best[ext=mp4][height<=360]/  (bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/   best[ext=mp4]   /bestvideo[ext=mp4]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/best)[protocol!=http_dash_segments][vcodec !^=? av01]'
worst_video_format = vid_nhd_format
audio_format = '((bestaudio[ext=m4a]/bestaudio[ext=mp3])[protocol^=http]/bestaudio/best[ext=mp4,height<=480]/best[ext=mp4]/best)[protocol!=http_dash_segments]'