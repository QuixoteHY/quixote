# -*- coding:utf-8 -*-
# @Time     : 2018-12-31 21:47
# @Author   : 胡远
# @Github   : https://github.com/QuixoteHY
# @Email    : 1290482442@qq.com
# @Describe : 引擎

import types
import asyncio

from quixote import loop
from quixote.protocol import Request, Response
from quixote.scraper import Scraper
from quixote import signals
from quixote.exceptions import CloseSpider
from quixote.logger import logger
from quixote.utils.misc import load_object
from quixote.utils.schedule_func import CallLaterOnce


class Heart(object):
    def __init__(self, start_requests, close_if_idle, next_call, scheduler):
        self.start_requests = iter(start_requests)
        self.close_if_idle = close_if_idle
        self.next_call = next_call
        self.scheduler = scheduler
        self.closing = False
        self.in_progress = set()

    def add_request(self, request):
        self.in_progress.add(request)

    def remove_request(self, request):
        self.in_progress.remove(request)
        self.heart_maybe_stop()

    def _heartbeat(self, interval):
        if self.closing:
            self.next_call.schedule()
            loop.call_later(interval, self._heartbeat, interval)

    def start(self, interval):
        self._heartbeat(interval)

    def close(self):
        self.closing = True
        self.heart_maybe_stop()
        return self.closing

    def heart_maybe_stop(self):
        if self.closing and not self.in_progress:
            if self.next_call:
                self.next_call.cancel()


class Engine(object):
    def __init__(self, starter):
        self.starter = starter
        self.settings = starter.settings
        self.signals = starter.signals
        self.heart = None
        self.spider = None
        self.scraper = Scraper(starter)
        self.scheduler_class = load_object(self.settings['SCHEDULER'])
        downloader_class = load_object(self.settings['DOWNLOADER'])
        self.downloader = downloader_class(starter)
        self.downloading = set()
        self.running = False
        self.paused = False

    def start(self, spider, close_if_idle=True):
        self.running = True
        self.signals.send(signals.engine_started, self)
        self.spider = spider
        next_call = CallLaterOnce(self._next_request, spider)
        scheduler = self.scheduler_class.from_starter(self.starter)
        start_requests = self.scraper.spidermw.process_start_requests(self.spider.start_requests(), spider)
        self.heart = Heart(start_requests, close_if_idle, next_call, scheduler)
        self.before_start_requests(self.spider)
        self.scraper.open_spider(spider)
        self.starter.stats.open_spider(spider)
        self.heart.next_call.schedule()
        self.heart.start(5)
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def close(self, reason):
        """Close the engine gracefully.
        :param reason:
        :return:
        """
        logger.info("Closing spider (%(reason)s)", {'reason': reason}, extra={'spider': self.spider})
        # 需要将各组件关闭逻辑封装到future对象中，并加上回调函数
        assert self.running, "Engine not running"
        self.running = False
        # asyncio.run_coroutine_threadsafe(self.downloader.close(), loop)
        # asyncio.run_coroutine_threadsafe(self.close_components(reason, self.spider), loop)
        self.signals.send(signals.spider_closed, self.spider)
        return self.close_components(reason, self.spider)

    def close_components(self, reason, spider):
        task = asyncio.ensure_future(self.downloader.close())
        task.add_done_callback(lambda f: logger.info("Spider closed (%(reason)s)", {'reason': reason},
                                                     extra={'spider': spider}))
        return {task}

    def _next_request(self, spider):
        if not self.heart:
            return
        if self.paused:
            return
        heart = self.heart
        while not self._needs_slowdown():
            if not self._next_request_from_scheduler(spider):
                break
        if heart.start_requests and not self._needs_slowdown():
            try:
                request = next(heart.start_requests)
            except StopIteration:
                heart.start_requests = None
            except Exception as e:
                heart.start_requests = None
                logger.error('Error while obtaining start requests', exc_info=True,
                             extra={'spider': spider, 'exc_info': str(e)})
            else:
                self.crawl(request, spider)
        if self.engin_is_idle() and heart.close_if_idle:
            self._ready_to_close()

    def engin_is_idle(self):
        if self.downloading:
            return False
        if not self.scraper.slot.is_idle():
            # scraper is not idle
            return False
        if self.downloader.active:
            # downloader has pending requests
            return False
        if self.heart.start_requests is not None:
            # not all start requests are handled
            return False
        if self.heart.scheduler.has_pending_requests():
            # scheduler has pending requests
            return False
        return True

    def _ready_to_close(self):
        if not self.engin_is_idle():
            return
        heart = self.heart
        if heart.closing:
            return heart.closing
        reason = 'finished'
        heart.close()
        loop.call_later(3, self.starter.close, reason)

    def _needs_slowdown(self):
        return self.downloader.needs_slowdown()

    def _next_request_from_scheduler(self, spider):
        heart = self.heart
        request = heart.scheduler.pop_request()
        if not request:
            return False
        self.downloading.add(request)
        asyncio.run_coroutine_threadsafe(self._download(request, spider), loop)
        return True

    async def _download(self, request, spider):
        try:
            self.heart.add_request(request)
            response = await self.downloader.fetch(request, spider)
            assert isinstance(response, (Response, Request))
            if isinstance(response, Response):
                response.request = request
            self.heart.next_call.schedule()
            self._handle_downloader_output(response, request, spider)
            # 需认真检查, 如果出现异常，预计会出现什么情况
            # self.heart.remove_request(request)
        except Exception as e:
            logger.error(logger.exception(e))
        finally:
            self.downloading.remove(request)
            self.heart.remove_request(request)
            self.heart.next_call.schedule()

    def _handle_downloader_output(self, response, request, spider):
        assert isinstance(response, (Request, Response)), response
        if isinstance(response, Request):
            self.crawl(response, spider)
            return
        # self.scraper.enqueue_scrape(response, request, spider)
        # call_later 第一个参数必须为0，否则request会在该回调函数执行完前从heart中清除掉，这块逻辑需要优化
        loop.call_later(0, self.scraper.enqueue_scrape, response, request, spider)

    def crawl(self, request, spider):
        assert spider in [self.spider], "Spider %r not opened when crawling: %s" % (spider.name, request)
        self.heart.scheduler.push_request(request)
        self.heart.next_call.schedule()

    def pause(self):
        self.paused = True

    def un_pause(self):
        self.paused = False

    def before_start_requests(self, spider):
        async def task(_request, _spider):
            try:
                response = await self.downloader.fetch(_request, _spider)
                if not isinstance(response, Response):
                    logger.error('The Download data was not a Response object')
                    return
                for item in _request.callback(response):
                    print(item)
            except Exception as e:
                logger.error(logger.exception(e))
                raise CloseSpider('before_start_requests error')
        start_requests = spider.before_start_requests()
        if not isinstance(start_requests, types.GeneratorType):
            return
        for request in start_requests:
            if not request:
                continue
            loop.run_until_complete(task(request, spider))
