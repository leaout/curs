# coding: utf-8
import unittest
from curs.news_context import headline_context


class NewsContextTests(unittest.TestCase):
    def test_exact_name_and_theme_evidence(self):
        result = headline_context('宁德时代发布储能产品', {'300750.SZ':'宁德时代'})
        self.assertEqual(result['stocks'][0]['evidence'], '宁德时代')
        self.assertEqual(result['themes'][0]['evidence'], ['储能'])

    def test_no_inferred_constituents_or_short_name(self):
        result = headline_context('银行与平安保险消息', {'601318.SH':'中国平安', '000001.SZ':'平安'})
        self.assertEqual(result['stocks'], [])

    def test_code_boundaries_and_english_word_boundaries(self):
        catalog = {'600519.SH':'贵州茅台'}
        self.assertEqual(headline_context('16005190 CHAIR', catalog)['stocks'], [])
        self.assertEqual(headline_context('CHAIR', catalog)['themes'], [])
        self.assertEqual(headline_context('600519.SH 公告 AI', catalog)['stocks'][0]['stock_code'], '600519.SH')
