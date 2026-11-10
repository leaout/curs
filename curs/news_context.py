# coding: utf-8
"""Explainable headline matching, not sector membership or investment advice."""

import re

THEMES = {
    '人工智能': ('人工智能', '大模型', '算力', 'AI'),
    '半导体': ('半导体', '芯片', '光刻', 'semiconductor'),
    '新能源': ('光伏', '锂电', '储能', '新能源汽车'),
    '机器人': ('机器人', '人形机器人', 'robotics'),
    '医药': ('创新药', '疫苗', '生物医药'),
    '金融': ('银行', '券商', '保险', '证券公司'),
    '地产': ('房地产', '楼市', '地产'),
    '资源': ('黄金', '稀土', '原油', '有色金属'),
}


def headline_context(title, catalog):
    text = str(title or '')
    themes = []
    for theme, keywords in THEMES.items():
        evidence = [word for word in keywords if (
            re.search(r'(?<![a-zA-Z])' + re.escape(word) + r'(?![a-zA-Z])', text, re.I)
            if word.isascii() else word in text)]
        if evidence:
            themes.append({'name':theme, 'evidence':evidence})
    stocks = []
    explicit_codes = {match.group(1):match.group(0) for match in re.finditer(
        r'(?<![\w])(\d{6})(?:\.(?:SH|SZ|BJ))?(?![\w])', text, re.I)}
    for code, name in catalog.items():
        if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', code):
            continue
        number = code[:6]
        code_match = explicit_codes.get(number)
        # Short names are ambiguous in prose: only associate them by explicit code.
        name_match = isinstance(name, str) and len(name) >= 4 and name in text
        if code_match or name_match:
            stocks.append({'stock_code':code, 'stock_name':name,
                           'evidence':code_match if code_match else name,
                           'basis':'标题明确代码' if code_match else '标题完整名称'})
    return {'themes':themes, 'stocks':stocks[:10],
            'disclaimer':'仅标题规则匹配；不是行业成分、利好判断或交易建议'}
