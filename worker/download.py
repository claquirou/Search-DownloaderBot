import asyncio
import functools
import inspect
import mimetypes
import os
import re
import sys
import traceback
from datetime import time, timedelta
from urllib.error import HTTPError
from urllib.parse import urlparse, urlunparse

import aiofiles
import youtube_dl
from aiogram import Bot
from telethon.errors import AuthKeyDuplicatedError, BadRequestError
from telethon.tl.types import (DocumentAttributeAudio,
                               DocumentAttributeFilename,
                               DocumentAttributeVideo)
from urlextract import URLExtract

from . import av_source, av_utils, cut_time, fast_telethon, tgaction, thumb, zip_file

# TOKEN = os.environ["TOKEN"]
TOKEN = "1930065720:AAGDIqnT5ruQZYQnPxtuZ5BNJOV2HmCxwGg"
_bot = Bot(TOKEN)

url_extractor = URLExtract()

TG_MAX_FILE_SIZE = 2000 * 1024 * 1024
TG_MAX_PARALLEL_CONNECTIONS = 20
TG_CONNECTIONS_COUNT = 0
MAX_STORAGE_SIZE = 2000 * 1024 * 1024
STORAGE_SIZE = MAX_STORAGE_SIZE


async def send_files(client, chat_id, message, cmd, log):
    try:
        msg_task = asyncio.get_event_loop().create_task(perform_task(client, chat_id, message, cmd, log))
        asyncio.get_event_loop().create_task(task_timeout_cancel(msg_task, timemout=21600))

    except Exception as e:
        print(e)
        traceback.print_exc()


async def task_timeout_cancel(task, timemout=5):
    try:
        await asyncio.wait_for(task, timeout=timemout)
    except asyncio.TimeoutError:
        task.cancel()


async def perform_task(client, chat_id, message, cmd, log):
    try:
        try:
            await download_file(client, chat_id, message, cmd, log)
        except HTTPError as e:
            # crashing to try change ip
            # otherwise youtube.com will not allow us
            # to download any video for some time
            if e.code == 429:
                log.critical(e)
                await shutdown(client)
            else:
                log.exception(e)
                await client.send_message(chat_id, e.__str__())
        except youtube_dl.DownloadError as e:
            # crashing to try change ip
            # otherwise youtube.com will not allow us
            # to download any video for some time
            if e.exc_info[0] is HTTPError:
                if e.exc_info[1].file.code == 429:
                    log.critical(e)
                    await shutdown(client)

            log.exception(e)
            await client.send_message(chat_id, str(e))
        except Exception as e:
            log.exception(e)
            if 'ERROR' not in str(e):
                err_msg = 'ERROR: ' + str(e)
            else:
                err_msg = str(e)
            await client.send_message(chat_id, err_msg)
    except Exception as e:
        log.error(e)


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


is_ytb_link_re = re.compile(
    r'^((?:https?:)?\/\/)?((?:www|m|music)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$')
get_ytb_id_re = re.compile(
    r'.*(youtu.be\/|v\/|embed\/|watch\?|youtube.com\/user\/[^#]*#([^\/]*?\/)*)\??v?=?([^#\&\?]*).*')


def youtube_to_invidio(url, audio=False):
    u = None
    if is_ytb_link_re.search(url):
        ytb_id_match = get_ytb_id_re.search(url)
        if ytb_id_match:
            ytb_id = ytb_id_match.groups()[-1]
            u = "https://invidious.snopyta.org/watch?v=" + ytb_id + "&quality=dash"
            if audio:
                u += '&listen=1'
    return u


async def upload_multipart_zip(client, source, name, file_size, chat_id, log):
    zfile = zip_file.ZipTorrentContentFile(source, name, file_size)

    async def upload_torrent_content(file):
        global TG_CONNECTIONS_COUNT
        global TG_MAX_PARALLEL_CONNECTIONS
        if 20 > TG_CONNECTIONS_COUNT and file.size > 100 * 1024 * 1024:
            TG_CONNECTIONS_COUNT += 2
            try:
                uploaded_file = await fast_telethon.upload_file(client,
                                                                file,
                                                                file_size=file.size,
                                                                file_name=file.name,
                                                                max_connection=2)
            finally:
                TG_CONNECTIONS_COUNT -= 2
        else:
            uploaded_file = await client.upload_file(file, file_size=file.size, file_name=file.name)

        await client.send_file(chat_id, uploaded_file, caption=str(chat_id))

    try:
        for _ in range(0, zfile.zip_parts):
            await upload_torrent_content(zfile)
            zfile.zip_num += 1
    except BadRequestError as e:
        log.error(e)

    if source is not None:
        if inspect.iscoroutinefunction(source.close):
            await source.close()
        else:
            source.close()


async def download_file(client, chat_id, message, cmd, log):
    global STORAGE_SIZE

    log.info(f"URL: {message}")
    urls = url_extractor.find_urls(message)

    if len(urls) == 0:
        await client.send_message(chat_id, "L'URL de la vidéo est incorrect.")
        return

    playlist_start = None
    playlist_end = None
    audio_mode = False

    # check cmd and choose video format    
    cut_time_start = cut_time_end = None

    if cmd == 'a':
        preferred_formats = [audio_format]
        audio_mode = True
    else:
        preferred_formats = [vid_hd_format, vid_nhd_format]

    async with tgaction.TGAction(_bot, chat_id, "upload_document"):
        urls = set(urls)
        for iu, u in enumerate(urls):
            vinfo = None
            params = {'youtube_include_dash_manifest': False,
                      'quiet': True,
                      'no_color': True,
                      'nocheckcertificate': True
                      # 'force_generic_extractor': True if 'invidious.snopyta.org/watch' in u else False
                      }

            if playlist_start is not None and playlist_end is not None:  # and 'invidious.snopyta.org/watch' not in u:
                params['ignoreerrors'] = True
                params['playliststart'] = playlist_start
                params['playlistend'] = playlist_end
            else:
              
                if chat_id in [711322052, 984343307]:
                    params['playliststart'] = 1
                    params['playlistend'] = 500
                else:
                    params['playliststart'] = 1
                    params['playlistend'] = 10

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
                                # try to use invidious.snopyta.org youtube frontend to bypass 429 block
                                if (e.exc_info is not None and e.exc_info[0] is HTTPError and e.exc_info[
                                    1].file.code == 429) or \
                                        'video available in your country' in str(e) or \
                                        'youtube age limit' == str(e):
                                    invid_url = youtube_to_invidio(u, audio_mode)
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

                if '_type' in vinfo and vinfo['_type'] == 'playlist':
                    entries = vinfo['entries']
                else:
                    entries = [vinfo]

                for ie, entry in enumerate(entries):
                    if entry is None:
                        try:
                            await client.send_message(chat_id,
                                                      f"ATTENTION: #{params['playliststart'] + ie} a été ignoré en "
                                                      f"raison d'une erreur")
                        except:
                            pass
                        continue

                    formats = entry.get('requested_formats')
                    _file_size = None
                    chosen_format = None
                    ffmpeg_av = None
                    http_headers = None

                    if 'http_headers' not in entry:
                        if formats is not None and 'http_headers' in formats[0]:
                            http_headers = formats[0]['http_headers']
                    else:
                        http_headers = entry['http_headers']

                    if not entry.get('direct', False):
                        http_headers['Referer'] = u

                    _title = entry.get('title', '')
                    if _title == '':
                        entry['title'] = "58450154"

                    _cut_time = (cut_time_start, cut_time_end) if cut_time_start else None
                    try:
                        if formats is not None:
                            for i, f in enumerate(formats):
                                if f['protocol'] in ['rtsp', 'rtmp', 'rtmpe', 'mms', 'f4m', 'ism',
                                                     'http_dash_segments']:
                                    continue

                                if 'm3u8' in f['protocol']:
                                    _file_size = await av_utils.m3u8_video_size(f['url'], http_headers)
                                else:
                                    if 'filesize' in f and f['filesize'] != 0 and f['filesize'] is not None and f[
                                        'filesize'] != 'none':
                                        _file_size = f['filesize']
                                    else:
                                        try:
                                            direct_url = f['url']
                                            if 'invidious.snopyta.org' in direct_url:
                                                direct_url = normalize_url_path(direct_url)
                                            _file_size = await av_utils.media_size(direct_url,
                                                                                   http_headers=http_headers)
                                        except Exception as e:
                                            if i < len(formats) - 1 and '404 Not Found' in str(e):
                                                break
                                            else:
                                                raise

                                # Dash video
                                if f['protocol'] == 'https' and \
                                        (True if ('acodec' in f and (
                                                f['acodec'] == 'none' or f['acodec'] is None)) else False):
                                    vformat = f
                                    mformat = None

                                    direct_url = vformat['url']
                                    if 'invidious.snopyta.org' in direct_url:
                                        vformat['url'] = normalize_url_path(direct_url)

                                    if 'filesize' in vformat and vformat['filesize'] != 0 and vformat[
                                        'filesize'] is not None and vformat['filesize'] != 'none':
                                        vsize = vformat['filesize']
                                    else:
                                        vsize = await av_utils.media_size(vformat['url'], http_headers=http_headers)
                                    msize = 0
                                    # if there is one more format than
                                    # it's likely an url to audio
                                    if len(formats) > i + 1:
                                        mformat = formats[i + 1]

                                        direct_url = mformat['url']
                                        if 'invidious.snopyta.org' in direct_url:
                                            mformat['url'] = normalize_url_path(direct_url)

                                        if 'filesize' in mformat and mformat['filesize'] != 0 and mformat[
                                            'filesize'] is not None and mformat['filesize'] != 'none':
                                            msize = mformat['filesize']
                                        else:
                                            msize = await av_utils.media_size(mformat['url'], http_headers=http_headers)

                                    # we can't precisely predict media size so make it large for prevent cutting
                                    _file_size = vsize + msize + 10 * 1024 * 1024
                                    if _file_size < TG_MAX_FILE_SIZE or cut_time_start is not None:
                                        file_name = None
                                        if not cut_time_start and STORAGE_SIZE > _file_size > 0:
                                            STORAGE_SIZE -= _file_size
                                            _ext = 'mp4' if audio_mode is False else 'mp3'
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
                                        (_file_size <= TG_MAX_FILE_SIZE or cut_time_start is not None)):
                                    chosen_format = f
                                    acodec = f.get('acodec')
                                    if acodec is None or acodec == 'none':
                                        if len(formats) > i + 1:
                                            mformat = formats[i + 1]
                                            if 'filesize' in mformat and mformat['filesize'] != 0 and mformat[
                                                'filesize'] is not None and mformat['filesize'] != 'none':
                                                msize = mformat['filesize']
                                            else:
                                                msize = await av_utils.media_size(mformat['url'],
                                                                                  http_headers=http_headers)
                                            msize += 10 * 1024 * 1024
                                            if (msize + _file_size) > TG_MAX_FILE_SIZE and cut_time_start is None:
                                                mformat = None
                                            else:
                                                _file_size += msize

                                    file_name = None
                                    if not cut_time_start and STORAGE_SIZE > _file_size > 0:
                                        STORAGE_SIZE -= _file_size
                                        _ext = 'mp4' if audio_mode is False else 'mp3'
                                        file_name = entry['title'] + '.' + _ext
                                    ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                aformat=mformat,
                                                                                audio_only=True if audio_mode else False,
                                                                                headers=http_headers,
                                                                                cut_time_range=_cut_time,
                                                                                file_name=file_name)
                                    break
                                # regular video stream
                                if (0 < _file_size <= TG_MAX_FILE_SIZE) or cut_time_start is not None:
                                    chosen_format = f

                                    direct_url = chosen_format['url']
                                    if 'invidious.snopyta.org' in direct_url:
                                        chosen_format['url'] = normalize_url_path(direct_url)

                                    if audio_mode and not (chosen_format['ext'] == 'mp3'):
                                        ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                    audio_only=True,
                                                                                    headers=http_headers,
                                                                                    cut_time_range=_cut_time)
                                    break

                        else:
                            if entry['protocol'] in ['rtsp', 'rtmp', 'rtmpe', 'mms', 'f4m', 'ism',
                                                     'http_dash_segments']:
                                recover_playlist_index = ie
                                break
                            if 'm3u8' in entry['protocol']:
                                if cut_time_start is None and entry.get('is_live',
                                                                        False) is False and audio_mode is False:
                                    _file_size = await av_utils.m3u8_video_size(entry['url'], http_headers=http_headers)
                                else:
                                    # we don't know real size
                                    _file_size = 0
                            else:
                                if 'filesize' in entry and entry['filesize'] != 0 and entry['filesize'] is not None and \
                                        entry['filesize'] != 'none':
                                    _file_size = entry['filesize']
                                else:
                                    direct_url = entry['url']
                                    if 'invidious.snopyta.org' in direct_url:
                                        entry['url'] = normalize_url_path(direct_url)

                                    try:
                                        _file_size = await av_utils.media_size(direct_url, http_headers=http_headers)
                                    except:
                                        _file_size = TG_MAX_FILE_SIZE

                            if ('m3u8' in entry['protocol'] and
                                    (_file_size <= TG_MAX_FILE_SIZE or cut_time_start is not None)):
                                chosen_format = entry
                                if entry.get('is_live') and not _cut_time:
                                    cut_time_start, cut_time_end = (time(hour=0, minute=0, second=0),
                                                                    time(hour=1, minute=0, second=0))
                                    _cut_time = (cut_time_start, cut_time_end)
                                file_name = None
                                if not cut_time_start and STORAGE_SIZE > _file_size > 0:
                                    STORAGE_SIZE -= _file_size
                                    _ext = 'mp4' if audio_mode is False else 'mp3'
                                    file_name = entry['title'] + '.' + _ext

                                ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                            audio_only=True if audio_mode else False,
                                                                            headers=http_headers,
                                                                            cut_time_range=_cut_time,
                                                                            file_name=file_name)
                            elif (_file_size <= TG_MAX_FILE_SIZE) or cut_time_start is not None:
                                chosen_format = entry
                                direct_url = chosen_format['url']
                                if 'invidious.snopyta.org' in direct_url:
                                    chosen_format['url'] = normalize_url_path(direct_url)
                                if audio_mode and not (chosen_format['ext'] == 'mp3'):
                                    ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                                audio_only=True,
                                                                                headers=http_headers,
                                                                                cut_time_range=_cut_time)

                        if chosen_format is None and ffmpeg_av is None:
                            if len(preferred_formats) - 1 == ip:
                                if _file_size > TG_MAX_FILE_SIZE:
                                    log.info(f"Fichier trop volumineux {file_size}")

                                    if 'http' in entry.get('protocol', '') and 'unknown' in entry.get('format',
                                                                                                      '') and entry.get(
                                        'ext', '') not in ['unknown_video', 'mp3', 'mp4', 'm4a', 'ogg', 'mkv',
                                                           'flv', 'avi', 'webm']:

                                        source = await av_source.URLav.create(entry.get('url'), http_headers)
                                        await upload_multipart_zip(client, source, f"{entry['title']}.{entry['ext']}",
                                                                   _file_size, chat_id, log)
                                    else:
                                        await client.send_message(chat_id,
                                                                  f"ERREUR: Taille de fichier multimédia trop grande **{sizeof_fmt(file_size)}**\nTelegram autorise les fichiers moins de **1.5GB**")

                                else:
                                    log.info('Echec de la recherche du format de support approprié')
                                    await client.send_message(chat_id,
                                                              "ERREUR: Echec de la recherche du format de support "
                                                              "approprié")
                                return

                            recover_playlist_index = ie
                            break

                        # if cmd == 'z' and ffmpeg_av is None:
                        #     await upload_multipart_zip(client, entry.get('url'), http_headers,
                        #                                entry['title'] + '.' + entry['ext'], _file_size, chat_id,
                        #                                msg_id)
                        #     return
                        if audio_mode and _file_size != 0 and (ffmpeg_av is None or ffmpeg_av.file_name is None):
                            # we don't know real size due to converting formats
                            # so increase it in case of real size is less large then estimated
                            _file_size += 10 * 1024 * 1024  # 10MB

                        log.debug('Fichier en cours de téléchargement...')
                        await client.send_message(chat_id,
                                                  "Votre fichier est en cours de telechargement. Patientez quelque "
                                                  "seconde.")

                        width = height = video_codec = audio_codec = None
                        title = performer = None
                        format_name = ''

                        if audio_mode:
                            if entry.get('duration') is None and chosen_format.get('duration') is None:
                                info = await av_utils.av_info(chosen_format['url'], http_headers=http_headers)
                                duration = int(float(info['format'].get('duration', 0)))
                            else:
                                duration = int(chosen_format['duration']) if 'duration' not in entry else int(
                                    entry['duration'])

                        elif (entry.get('duration') is None and chosen_format.get('duration') is None) or \
                                (chosen_format.get('width') is None or chosen_format.get('height') is None):

                            info = await av_utils.av_info(chosen_format['url'], http_headers=http_headers)
                            try:
                                streams = info['streams']
                                for s in streams:
                                    if s.get('codec_type') == 'video':
                                        width = s['width']
                                        height = s['height']
                                        video_codec = s['codec_name']
                                    elif s.get('codec_type') == 'audio':
                                        audio_codec = s['codec_name']
                                if video_codec is None:
                                    audio_mode = True
                                _av_format = info['format']
                                duration = int(float(_av_format.get('duration', 0)))
                                format_name = _av_format.get('format_name', '').split(',')[0]
                                av_tags = _av_format.get('tags')
                                if av_tags is not None and len(av_tags.keys()) > 0:
                                    title = av_tags.get('title')
                                    performer = av_tags.get('artist')
                                    if performer is None:
                                        performer = av_tags.get('album')
                                _av_ext = chosen_format.get('ext', '')
                                if _av_ext == 'mp3' or _av_ext == 'm4a' or _av_ext == 'ogg' or format_name == 'mp3' or format_name == 'ogg':
                                    audio_mode = True
                            except KeyError:
                                width = 0
                                height = 0
                                duration = 0
                                format_name = ''
                        else:
                            width, height, duration = chosen_format['width'], chosen_format['height'], \
                                                      int(chosen_format[
                                                              'duration']) if 'duration' not in entry else int(
                                                          entry['duration'])
                        if 'm3u8' in chosen_format.get('protocol',
                                                       '') and duration == 0 and ffmpeg_av is not None and cut_time_start is None:
                            cut_time_start, cut_time_end = (time(hour=0, minute=0, second=0),
                                                            time(hour=1, minute=0, second=0))
                            _cut_time = (cut_time_start, cut_time_end)
                            ffmpeg_av.close()
                            ffmpeg_av = None

                        if 'mp4 - unknown' in chosen_format.get('format', '') and chosen_format.get('ext', '') != 'mp4':
                            chosen_format['ext'] = 'mp4'
                        elif 'unknown' in chosen_format['ext'] or 'php' in chosen_format['ext']:
                            mime, cd_file_name = await av_utils.media_mime(chosen_format['url'],
                                                                           http_headers=http_headers)
                            if cd_file_name:
                                cd_splited_file_name, cd_ext = os.path.splitext(cd_file_name)
                                if len(cd_ext) > 0:
                                    chosen_format['ext'] = cd_ext[1:]
                                else:
                                    chosen_format['ext'] = ''
                                if len(cd_splited_file_name) > 0:
                                    chosen_format['title'] = cd_splited_file_name
                            else:
                                ext = mimetypes.guess_extension(mime)
                                if ext is None or ext == '' or ext == '.bin':
                                    if format_name is None or format_name == '':
                                        chosen_format['ext'] = 'bin'
                                    else:
                                        if format_name == 'mov':
                                            if audio_mode:
                                                format_name = 'm4a'
                                            else:
                                                format_name = 'mp4'
                                        if format_name == 'matroska':
                                            format_name = 'mkv'
                                        chosen_format['ext'] = format_name
                                else:
                                    ext = ext[1:]
                                    chosen_format['ext'] = ext

                        # in case of video is live we don't know real duration
                        if cut_time_start is not None:
                            if not entry.get('is_live') and duration > 1:
                                if cut_time.time_to_seconds(cut_time_start) > duration:
                                    await client.send_message(chat_id,
                                                              f"ERROR: L'heure de début est plus longue que la durée du fichier **{timedelta(seconds=duration)}**")
                                    return
                                elif cut_time_end is not None and (
                                        cut_time.time_to_seconds(cut_time_end) > duration != 0):
                                    await client.send_message(chat_id,
                                                              f"ERROR: L'heure de fin est plus longue que la durée du fichier **{timedelta(seconds=duration)}**")
                                    return

                            if cut_time_end is None:
                                if duration == 0:
                                    duration = 20000
                                duration = abs(duration - cut_time.time_to_seconds(cut_time_start))
                            else:
                                duration = abs(
                                    cut_time.time_to_seconds(cut_time_end) - cut_time.time_to_seconds(cut_time_start))

                        if (cut_time_start is not None or (audio_mode and (
                                chosen_format.get('ext') not in ['mp3', 'm4a', 'ogg']))) and ffmpeg_av is None:
                            ext = chosen_format.get('ext')
                            ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                        headers=http_headers,
                                                                        cut_time_range=_cut_time,
                                                                        ext=ext,
                                                                        audio_only=True if audio_mode else False,
                                                                        format_name=format_name if ext != 'mp4' and format_name != '' else '')

                        if cmd == 'm' and chosen_format.get('ext') != 'mp4' and ffmpeg_av is None and (
                                video_codec == 'h264' or video_codec == 'hevc') and \
                                (audio_codec == 'mp3' or audio_codec == 'aac'):
                            file_name = entry.get('title', 'default') + '.mp4'
                            if STORAGE_SIZE > _file_size > 0:
                                STORAGE_SIZE -= _file_size
                                ffmpeg_av = await av_source.FFMpegAV.create(chosen_format,
                                                                            headers=http_headers,
                                                                            file_name=file_name)
                        upload_file = ffmpeg_av if ffmpeg_av is not None else await av_source.URLav.create(
                            chosen_format['url'],
                            http_headers)

                        ext = (
                            chosen_format['ext'] if ffmpeg_av is None or ffmpeg_av.format is None else ffmpeg_av.format)
                        file_name_no_ext = entry['title']
                        if not file_name_no_ext[-1].isalnum():
                            file_name_no_ext = file_name_no_ext[:-1] + '_'
                        file_name = file_name_no_ext + '.' + ext
                        if _file_size == 0:
                            log.warning('Taille de fichier est égal à 0.')

                        file_size = _file_size if _file_size != 0 and _file_size < TG_MAX_FILE_SIZE else TG_MAX_FILE_SIZE

                        ffmpeg_cancel_task = None
                        if ffmpeg_av is not None:
                            cancel_time = 20000
                            if cut_time_start is not None:
                                cancel_time += duration + 300
                            ffmpeg_cancel_task = asyncio.get_event_loop().call_later(cancel_time, ffmpeg_av.safe_close)
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
                            if (file_size > 20 * 1024 * 1024 and TG_CONNECTIONS_COUNT < TG_MAX_PARALLEL_CONNECTIONS) and \
                                    (isinstance(upload_file, av_source.URLav) or
                                     isinstance(upload_file, aiofiles.threadpool.binary.AsyncBufferedReader)):
                                try:
                                    connections = 2
                                    if TG_CONNECTIONS_COUNT < 12 and file_size > 100 * 1024 * 1024:
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
                        except ConnectionError as e:
                            if 'Cannot send requests while disconnected' in str(e):
                                await client.connect()
                                continue
                            raise
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

                        if audio_mode:
                            if performer is None:
                                performer = entry['artist'] if ('artist' in entry) and \
                                                               (entry['artist'] is not None) else None
                            if title is None:
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
                        if ext != 'mp4' and audio_mode is False:
                            force_document = True

                        log.debug('Envoie du fichier.')

                        video_note = False if audio_mode or force_document else True
                        voice_note = True if audio_mode else False
                        attributes = ((attributes,) if not force_document else None)
                        caption = entry['title']
                        recover_playlist_index = None
                        _thumb = None
                        try:
                            _thumb = await thumb.get_thumbnail(entry.get('thumbnail'), chosen_format)
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


async def shutdown(client):
    await client.disconnect()
    sys.exit(1)


vid_hd_format = '((best[ext=mp4][height<=720][height>360])[protocol^=http]/best[ext=mp4][height<=720][height>360]/  (bestvideo[ext=mp4][height<=720][height>360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=720][height>360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=720][height>360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio) /  (best[ext=mp4][height<=360])[protocol^=http]/best[ext=mp4][height<=360]/  (bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/   best[ext=mp4]   /bestvideo[ext=mp4]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/best)[protocol!=http_dash_segments][vcodec !^=? av01]'
vid_nhd_format = '((best[ext=mp4][height<=360])[protocol^=http]/best[ext=mp4][height<=360]/  (bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio))[protocol^=http]/(bestvideo[ext=mp4][height<=360])[protocol^=http]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/bestvideo[ext=mp4][height<=360]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/   best[ext=mp4]   /bestvideo[ext=mp4]+(bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio)/best)[protocol!=http_dash_segments][vcodec !^=? av01]'
worst_video_format = vid_nhd_format
audio_format = '((bestaudio[ext=m4a]/bestaudio[ext=mp3])[protocol^=http]/bestaudio/best[ext=mp4,height<=480]/best[ext=mp4]/best)[protocol!=http_dash_segments]'
