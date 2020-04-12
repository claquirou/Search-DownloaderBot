import asyncio
import json
from http.client import responses
from urllib.parse import urlparse

import m3u8
from aiohttp import ClientSession, hdrs


# convert each key-value to string like "key: value"
def dict_to_list(_dict):
    ret = []
    for k, v in _dict.items():
        ret.append(k + ": " + v)

    return ret

async def av_info(url, http_headers=''):
    info = await _av_info(url, http_headers)
    if len(info.keys()) == 0:
        # some sites return error if headers was passed
        info = await _av_info(url)

    return info

async def _av_info(url, http_headers=''):

    mediainf_args = None

    if http_headers != '':
        http_headers = '\n'.join(dict_to_list(http_headers))

    ff_proc = await asyncio.create_subprocess_exec('ffprobe',
                                                   '-v',
                                                   'error',
                                                   '-select_streams',
                                                   'v',
                                                   '-show_entries',
                                                   'stream=width,height',
                                                   '-show_entries',
                                                   'format=duration,format_name',
                                                   '-of',
                                                   'json',
                                                   '-headers',
                                                   http_headers,
                                                   url,
                                                   stdout=asyncio.subprocess.PIPE)

    out = await ff_proc.stdout.read()
    info = json.loads(out)
    if 'format' in info and 'duration' in info['format']:
        info['format']['duration'] = int(float(info['format']['duration']))
    return info

async def media_size(url, session=None, http_headers=None):
    content_length = None
    try:
        content_length = await _media_size(url, session, http_headers)
    except Exception as e:
        print(e)

    if content_length is not None:
        return content_length

    return await _media_size(url, session)

async def _media_size(url, session=None, http_headers=None):
    _session = None
    if session is None:
        _session = await ClientSession().__aenter__()
    else:
        _session = session
    content_length = 0
    try:
        async with _session.head(url, headers=http_headers, allow_redirects=True) as resp:
            if resp.status != 200:
                print('Request to url {} failed: '.format(url) + responses[resp.status])
            else:
                content_length = int(resp.headers.get(hdrs.CONTENT_LENGTH, '0'))

        # try GET request when HEAD failed
        if content_length < 100:
            async with _session.get(url, headers=http_headers) as get_resp:
                if get_resp.status != 200:
                    raise Exception('Request failed: ' + str(get_resp.status) + " " + responses[get_resp.status])
                else:
                    content_length = int(get_resp.headers.get(hdrs.CONTENT_LENGTH, '0'))
    finally:
        if session is None:
            await _session.__aexit__(exc_type=None, exc_val=None, exc_tb=None)

    return content_length
    # head_req = request.Request(url, method='HEAD', headers=http_headers)
    # try:
    #     with request.urlopen(head_req) as resp:
    #         return int(resp.headers['Content-Length'])
    # except:
    #     return None


async def media_mime(url, http_headers=None):
    async with ClientSession() as session:
        async with session.head(url, headers=http_headers, allow_redirects=True) as resp:
            media_type = ''
            content_type = resp.content_type
            if content_type:
                media_type = content_type.split('/')[0]
            if media_type != 'audio' and media_type != 'video':
                async with session.get(url, headers=http_headers) as get_resp:
                    _content_type = get_resp.headers.getall(hdrs.CONTENT_TYPE)
                    for ct in _content_type:
                        _media_type = ct.split('/')[0]
                        if _media_type == 'audio' or _media_type == 'video':
                            return ct

            return content_type if content_type is not None else ''


def m3u8_parse_url(url):
    _url = urlparse(url)
    if not _url.path.endswith('m3u8'):
        return url
    else:
        return m3u8._parsed_url(url) + '/'


async def m3u8_video_size(url, http_headers=None):
    m3u8_data = None
    m3u8_obj = None
    async with ClientSession() as session:
        async with session.get(url, headers=http_headers) as resp:
            m3u8_data = await resp.read()
            m3u8_obj = m3u8.loads(m3u8_data.decode())
            m3u8_obj.base_uri = m3u8_parse_url(str(resp.url))
        size = 0
        for seg in m3u8_obj.segments:
            size += await media_size(seg.absolute_uri, session=session, http_headers=http_headers)

    return size
