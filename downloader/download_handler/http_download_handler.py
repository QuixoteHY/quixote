# -*- coding:utf-8 -*-
# @Time     : 2019-01-15 22:47
# @Author   : 胡远
# @Github   : https://github.com/QuixoteHY
# @Email    : 1290482442@qq.com
# @Describe :

import asyncio
import aiohttp

from quixote.protocol.response import Response


class HTTPDownloadHandler(object):
    def __init__(self, settings):
        print(settings['DOWNLOAD_HANDLERS']['http'])

    def download_request(self, request, spider):
        task = asyncio.ensure_future(self.download(request, spider))
        task.add_done_callback(self.downloaded)
        return task

    @staticmethod
    def downloaded(future):
        print('Downloaded {}'.format(future.result().request.url))

    @staticmethod
    async def download(request, spider):
        await asyncio.sleep(2)
        return Response(spider.name+': '+request.url, request)

    @staticmethod
    async def get(url, headers=None, cookies=None, proxy=None, timeout=10):
        if cookies:
            session = aiohttp.ClientSession(cookies=cookies)
        else:
            session = aiohttp.ClientSession()
        if proxy:
            response = await session.get(url, headers=headers, proxy=proxy, timeout=timeout)
        else:
            response = await session.get(url, headers=headers, timeout=timeout)
        await session.close()
        return response

    @staticmethod
    async def post(url, headers=None, data=None, cookies=None, proxy=None, timeout=10):
        if cookies:
            session = aiohttp.ClientSession(cookies=cookies)
        else:
            session = aiohttp.ClientSession()
        if proxy:
            response = await session.post(url, headers=headers, data=data, proxy=proxy, timeout=timeout)
        else:
            response = await session.post(url, headers=headers, data=data, timeout=timeout)
        await session.close()
        return response