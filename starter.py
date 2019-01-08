# -*- coding:utf-8 -*-
# @Time     : 2019-01-02 21:13
# @Author   : 胡远
# @Github   : https://github.com/QuixoteHY
# @Email    : 1290482442@qq.com
# @Describe : 爬虫启动器

import logging
import time
from threading import Thread

import asyncio

from quixote.settings import Settings
from quixote import loop
from quixote.utils.misc import load_object

logger = logging.getLogger(__name__)


class Starter(object):
    def __init__(self, spider_class, settings_class=None):
        if settings_class:
            self.settings = Settings(load_object(settings_class)).get_settings()
        else:
            from quixote.settings import settings
            self.settings = Settings(settings).get_settings()
        print(self.settings)
        self.engine_class = load_object(self.settings['ENGINE'])
        self.spider_class = load_object(spider_class)
        self.engine = None
        self.spider = None
        self.crawling = False
        self.now = lambda: time.time()

    @staticmethod
    def _start():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def start(self):
        start = self.now()
        # t = Thread(target=self._start)
        # t.setDaemon(True)
        # t.start()
        print('TIME: {}'.format(self.now() - start))
        try:
            self.spider = self._create_spider()
            self.engine = self._create_engine()
            self.engine.start(self.spider)
        except KeyboardInterrupt as e:
            print('$$$$$$$$'+str(e))
            loop.stop()

    def _create_spider(self, *args, **kwargs):
        return self.spider_class.from_crawler(self, *args, **kwargs)

    def _create_engine(self):
        return self.engine_class(self)


def main():
    s = Starter('quixote.test.test_spider.TestSpider')
    s.start()


if __name__ == '__main__':
    main()
