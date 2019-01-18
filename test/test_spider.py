# -*- coding:utf-8 -*-
# @Time     : 2018-12-31 21:23
# @Author   : 胡远
# @Github   : https://github.com/QuixoteHY
# @Email    : 1290482442@qq.com
# @Describe : 测试爬虫

import time

from quixote import Spider, Request


class TestSpider(Spider):
    name = 'test'
    count = 1

    def start_requests(self):
        url_list = ['http://localhost:8000/reverse/0', 'http://localhost:8000/reverse/1']
        for url in url_list:
            yield Request(url=url, callback=self.parse)
        while True:
            self.count += 1
            yield Request(url='http://localhost:8000/reverse/' + str(self.count), callback=self.parse)

    def parse(self, response):
        time.sleep(0.05)
        yield response.content
        # num = 0
        # while True:
        #     num += 1
        #     if num == 3:
        #         break
        #     self.count += 1
        #     yield Request(url='https://github.com/QuixoteHY/'+str(self.count), callback=self.parse)


if __name__ == '__main__':
    s = TestSpider()
    ss = iter(s.start_requests())
    while True:
        print(next(ss).url)
