import akshare as ak
import pandas as pd
from datetime import datetime
import json
import requests
import re
import psycopg2
from bs4 import BeautifulSoup
import random

# ==================== 代理配置 ====================
PROXY_CONFIG = {
    'enabled': True,  # 是否启用代理
    'proxy_type': 'http',  # 代理类型：http/https/socks5
    'proxy_host': '192.168.100.1',
    'proxy_port': '7890',
    'timeout': 10,  # 超时时间
    'retry_times': 3,  # 重试次数
    'use_random_user_agent': True  # 是否使用随机User-Agent
}

# 用户代理列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
]

def get_proxy_config():
    """获取代理配置"""
    if not PROXY_CONFIG['enabled']:
        return None
    
    proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
    return {
        'http': proxy_url,
        'https': proxy_url,
    }

def get_random_user_agent():
    """获取随机User-Agent"""
    if PROXY_CONFIG['use_random_user_agent']:
        return random.choice(USER_AGENTS)
    return USER_AGENTS[0]  # 默认使用第一个

def make_request_with_proxy(url, method='GET', params=None, data=None, json_data=None, headers=None, timeout=None, retry_count=0):
    """
    带代理和重试机制的请求函数
    
    Args:
        url: 请求URL
        method: 请求方法（GET/POST）
        params: URL参数
        data: 表单数据
        json_data: JSON数据
        headers: 请求头
        timeout: 超时时间
        retry_count: 当前重试次数
        
    Returns:
        Response对象或None
    """
    if timeout is None:
        timeout = PROXY_CONFIG['timeout']
    
    # 设置默认headers
    if headers is None:
        headers = {}
    
    # 添加User-Agent
    if 'User-Agent' not in headers:
        headers['User-Agent'] = get_random_user_agent()
    
    # 获取代理配置
    proxies = get_proxy_config()
    
    try:
        if method.upper() == 'GET':
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                proxies=proxies, 
                timeout=timeout,
                verify=False  # 如果代理有证书问题可以关闭验证
            )
        elif method.upper() == 'POST':
            response = requests.post(
                url, 
                params=params,
                data=data,
                json=json_data,
                headers=headers, 
                proxies=proxies, 
                timeout=timeout,
                verify=False
            )
        else:
            raise ValueError(f"不支持的请求方法: {method}")
        
        response.raise_for_status()  # 检查HTTP错误
        return response
        
    except requests.exceptions.ProxyError as e:
        print(f"代理连接失败: {e}")
        if retry_count < PROXY_CONFIG['retry_times']:
            print(f"重试请求 ({retry_count + 1}/{PROXY_CONFIG['retry_times']})...")
            return make_request_with_proxy(url, method, params, data, json_data, headers, timeout, retry_count + 1)
        else:
            print(f"代理请求失败，达到最大重试次数")
            return None
            
    except requests.exceptions.ConnectTimeout as e:
        print(f"连接超时: {e}")
        if retry_count < PROXY_CONFIG['retry_times']:
            print(f"重试请求 ({retry_count + 1}/{PROXY_CONFIG['retry_times']})...")
            return make_request_with_proxy(url, method, params, data, json_data, headers, timeout, retry_count + 1)
        else:
            print(f"连接超时，达到最大重试次数")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None

def format_stock_code(original_code: str) -> str:
    """
    将原始代码（如SZ002261/SH603000）转换为目标格式（如002261.SZ/603000.SH）
    
    Args:
        original_code: 接口返回的原始代码（如SZ002261）
        
    Returns:
        格式化后的代码（如002261.SZ）
    """
    if pd.isna(original_code):
        return original_code
    
    original_code = str(original_code)
    
    # 处理已经包含BJ（北交所）的情况
    if original_code.startswith(('SH', 'SZ', 'BJ')):
        market = original_code[:2]
        code_num = original_code[2:]
        return f"{code_num}.{market}"
    elif '.' in original_code:  # 已经是目标格式
        return original_code
    elif original_code.startswith('1.') or original_code.startswith('0.'):
        # 处理东财的内部格式，如1.600000
        if original_code.startswith('1.'):
            code_num = original_code[2:8]  # 取6位数字
            return f"{code_num}.SH"
        elif original_code.startswith('0.'):
            code_num = original_code[2:8]  # 取6位数字
            return f"{code_num}.SZ"
    else:
        return original_code  # 非A股格式直接返回

def convert_to_stock_code(num):
    """
    转换东财内部格式为股票代码
    格式化为6位小数，提取小数部分，根据数字大小添加后缀
    """
    # 格式化为6位小数，提取小数部分
    fractional = f"{num:.6f}".split('.')[1]
    # 根据数字大小添加后缀
    return f"{fractional}.SZ" if num < 1 else f"{fractional}.SH"

def get_stock_concept_rot_rank():
    """
    获取概念轮动排名数据（使用代理）
    """
    url = 'https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate?'
    params = {'type': 'concept'}
    
    headers = {
        'Referer': 'https://stock.10jqka.com.cn/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    try:
        print("正在获取概念轮动排名数据...")
        response = make_request_with_proxy(url, 'GET', params=params, headers=headers)
        
        if response is None:
            print('概念轮动排名数据获取失败：请求失败')
            return pd.DataFrame()
        
        text = response.json()
        status_code = text.get('status_code', '')
        
        if int(status_code) == 0:
            df = pd.DataFrame(text['data']['plate_list'])
            df = df.rename(columns={"code":"概念代码", "name":"概念名称"})
            df['数据来源'] = '概念轮动排名'
            print(f"成功获取 {len(df)} 个概念数据")
            return df
        else:
            print(f'概念轮动排名数据获取失败，状态码: {status_code}')
            return pd.DataFrame()
    except Exception as e:
        print(f"获取概念轮动排名数据时发生错误: {e}")
        return pd.DataFrame()

def filter_high_volume_stocks(stock_code, volume_multiple=1.5, window=5):
    """
    过滤高成交量股票
    """
    # 注意：这个函数需要依赖get_kdata函数，目前先返回True（后续可自行实现）
    # 简化为直接返回True，避免依赖缺失
    return True

def getUtandeFields() -> dict:
    """
    获取东财API所需的参数（使用代理）
    """
    headers = {
        'Referer': 'https://vipmoney.eastmoney.com/collect/stockranking/pages/ranking/list.html',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    ut_fields = {}
    url = "https://vipmoney.eastmoney.com/collect/stockranking/static/script/ranking_list.js?01211021_1.0.2"
    params = {
        '01211021_1.0.2': ''
    }
    
    try:
        response = make_request_with_proxy(url, 'GET', params=params, headers=headers)
        
        if response is None:
            print("获取UT参数失败：请求失败")
            return {}
        
        content = response.text
        
        # 使用正则表达式提取参数
        ut_match = re.search(r'ut:"(.*?)"', content)
        fields_match = re.search(r'fields:"(.*?)"', content)
        globalId_match = re.search(r'globalId:"(.*?)"', content)
        
        if ut_match and fields_match and globalId_match:
            ut_fields['ut'] = ut_match.group(1)
            ut_fields['fields'] = fields_match.group(1)
            ut_fields['globalId'] = globalId_match.group(1)
            return ut_fields
        else:
            print("获取UT参数失败：未找到所需参数")
            return {}
    except Exception as e:
        print(f"获取UT参数失败: {e}")
        return {}

def getSecids(ut_fields: dict) -> str:
    """
    获取股票secids列表（使用代理）
    """
    url = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
    headers = {
        'Referer': 'https://vipmoney.eastmoney.com/collect/stockranking/pages/ranking/list.html',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': 'https://vipmoney.eastmoney.com',
        'Host': 'emappdata.eastmoney.com',
    }
    
    data = {
        'appId': 'appId01',
        'globalId': ut_fields['globalId'],
        'pageNo': '1',
        'pageSize': '100',
    }
    
    try:
        response = make_request_with_proxy(url, 'POST', json_data=data, headers=headers)
        
        if response is None:
            print("获取secids失败：请求失败")
            return ""
        
        jsData = json.loads(response.text)
        
        if 'data' not in jsData:
            print("获取secids失败：响应中无data字段")
            return ""
        
        jsData = jsData['data']
        secids = ""
        gb = 0
        for item in jsData:
            gb += 1
            sc = item['sc']
            if "SH" in sc:
                secids += sc.replace("SH", "1.") + ","
                if gb == len(jsData):
                    secids += sc.replace("SH", "1.")
            else:
                secids += sc.replace("SZ", "0.") + ","
                if gb == len(jsData):
                    secids += sc.replace("SZ", "0.")
        return secids
    except Exception as e:
        print(f"获取secids失败: {e}")
        return ""

def get_xueqiu_hot_stocks():
    """
    获取雪球热门关注股票数据（使用代理）
    """
    print("开始获取雪球热门关注股票数据...")
    try:
        # 配置akshare使用代理
        if PROXY_CONFIG['enabled']:
            proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
            # 设置环境变量让akshare使用代理
            import os
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
        
        # 获取雪球热门关注数据
        xq_df = ak.stock_hot_tweet_xq(symbol="本周新增")
        
        # 重命名列名以统一格式
        xq_df = xq_df.rename(columns={
            '股票代码': '代码',
            '股票简称': '股票名称',
            '关注': '关注度',
            '最新价': '最新价'
        })
        
        # 添加数据来源标记
        xq_df['数据来源'] = '雪球热门关注'
        
        # 格式化股票代码
        xq_df['格式化代码'] = xq_df['代码'].apply(format_stock_code)
        
        # 过滤掉688,300和.BJ结尾的股票
        xq_df = xq_df[~xq_df['格式化代码'].str.endswith('.BJ')]
        xq_df = xq_df[~xq_df['格式化代码'].str.startswith('688')]
        xq_df = xq_df[~xq_df['格式化代码'].str.startswith('30')]
        
        print(f"成功获取 {len(xq_df)} 只雪球热门关注股票")
        return xq_df
        
    except Exception as e:
        print(f"获取雪球数据时发生错误: {e}")
        return pd.DataFrame()

def get_eastmoney_hot_stocks():
    """
    获取东方财富热点股票排名数据（使用代理）
    """
    print("开始获取东方财富热点股票数据...")
    try:
        # 配置akshare使用代理
        if PROXY_CONFIG['enabled']:
            proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
            import os
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
        
        # 获取东方财富热点股票排名
        em_df = ak.stock_hot_rank_em()
        
        # 添加数据来源标记
        em_df['数据来源'] = '东方财富热点排名'
        
        # 格式化股票代码
        em_df['格式化代码'] = em_df['代码'].apply(format_stock_code)
        
        # 过滤掉688,300和.BJ结尾的股票
        em_df = em_df[~em_df['格式化代码'].str.endswith('.BJ')]
        em_df = em_df[~em_df['格式化代码'].str.startswith('688')]
        em_df = em_df[~em_df['格式化代码'].str.startswith('30')]
        
        print(f"成功获取 {len(em_df)} 只东方财富热点股票")
        return em_df
        
    except Exception as e:
        print(f"获取东方财富数据时发生错误: {e}")
        return pd.DataFrame()

def get_baidu_hot_search():
    """
    获取百度热搜股票数据（使用代理）
    """
    print("开始获取百度热搜股票数据...")
    try:
        # 获取当前日期
        current_date = datetime.now().strftime("%Y%m%d")
        
        # 配置akshare使用代理
        if PROXY_CONFIG['enabled']:
            proxy_url = f"{PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}"
            import os
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
        
        # 获取百度热搜股票数据
        baidu_df = ak.stock_hot_search_baidu(symbol="A股", date=current_date, time="今日")
        
        # 重命名列名以统一格式
        baidu_df = baidu_df.rename(columns={
            '名称/代码': '股票名称',
            '涨跌幅': '涨跌幅',
            '综合热度': '热搜热度'
        })
        
        # 分离股票名称和代码
        baidu_df['股票名称'] = baidu_df['股票名称'].str.split().str[0]
        baidu_df['代码'] = baidu_df['股票名称']  # 百度数据没有代码，暂时用名称代替
        
        # 添加数据来源标记
        baidu_df['数据来源'] = '百度热搜'
        
        # 格式化股票代码（百度没有标准代码，暂时用名称）
        baidu_df['格式化代码'] = baidu_df['股票名称']
        
        print(f"成功获取 {len(baidu_df)} 只百度热搜股票")
        return baidu_df
        
    except Exception as e:
        print(f"获取百度热搜数据时发生错误: {e}")
        return pd.DataFrame()

def get_dongcai_ranking_stocks():
    """
    获取东财内部API的热门股票（使用代理）
    """
    print("开始获取东财内部排名股票数据...")
    try:
        ut_fields = getUtandeFields()
        if not ut_fields:
            return []
            
        secids = getSecids(ut_fields)
        if not secids:
            return []
            
        # 转换所有数据
        numbers = [float(x) for x in secids.split(',') if x]
        converted_list = [convert_to_stock_code(num) for num in numbers]
        
        print(f"成功获取东财内部排名股票 {len(converted_list)} 只")
        return converted_list
        
    except Exception as e:
        print(f"获取东财内部排名股票时发生错误: {e}")
        return []

def filter_limit_down_stocks(stock_list):
    """
    过滤跌停股票
    """
    # 这里可以添加跌停股票过滤逻辑
    # 暂时返回原列表
    return stock_list

def save_to_database(stock_list):
    """
    保存股票列表到数据库
    """
    try:
        conn = psycopg2.connect(
            host="192.168.68.150",
            port="6432",
            database="postgres",
            user="postgres",
            password="chenly.1"
        )
        cur = conn.cursor()
        
        # 检查表是否存在
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'thx_stocks'
            )
        """)
        if not cur.fetchone()[0]:
            print("警告: thx_stocks表不存在，跳过数据库保存")
            cur.close()
            conn.close()
            return
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 插入数据
        inserted_count = 0
        for stock in stock_list:
            try:
                cur.execute(
                    "INSERT INTO thx_stocks (trade_date, stock_code) VALUES (%s, %s)",
                    (today, stock)
                )
                inserted_count += 1
            except psycopg2.IntegrityError:
                conn.rollback()  # 忽略重复插入
                continue
                
        conn.commit()
        cur.close()
        conn.close()
        print(f"成功保存 {inserted_count} 条记录到数据库")
        
    except Exception as e:
        print(f"数据库操作出错: {e}")

def test_proxy_connection():
    """测试代理连接"""
    print("测试代理连接...")
    
    test_url = "http://httpbin.org/ip"
    response = make_request_with_proxy(test_url, 'GET')
    
    if response:
        try:
            ip_info = response.json()
            print(f"代理连接成功！当前IP: {ip_info.get('origin', '未知')}")
            return True
        except:
            print("代理连接成功，但无法解析IP信息")
            return True
    else:
        print("代理连接失败！")
        
        # 尝试无代理连接
        try:
            response = requests.get(test_url, timeout=5)
            ip_info = response.json()
            print(f"直接连接成功！当前IP: {ip_info.get('origin', '未知')}")
            print("将使用无代理模式")
            PROXY_CONFIG['enabled'] = False
            return True
        except:
            print("网络连接失败，请检查网络设置")
            return False

def main():
    try:
        # 测试代理连接
        if PROXY_CONFIG['enabled']:
            if not test_proxy_connection():
                print("警告：代理连接测试失败，继续运行但可能无法获取数据")
        
        # 获取当前时间戳
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.now().strftime("%Y%m%d")
        
        print(f"开始获取多源热点股票数据... 时间: {current_time}")
        print(f"代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}")
        if PROXY_CONFIG['enabled']:
            print(f"代理地址: {PROXY_CONFIG['proxy_type']}://{PROXY_CONFIG['proxy_host']}:{PROXY_CONFIG['proxy_port']}")
        print("="*60)
        
        # 1. 获取东方财富热点数据
        em_df = get_eastmoney_hot_stocks()
        
        # 2. 获取雪球热门关注数据（只取前100只）
        xq_df = get_xueqiu_hot_stocks()
        if not xq_df.empty:
            xq_df = xq_df.head(100)  # 只取前100只
        
        # 3. 获取百度热搜数据
        baidu_df = get_baidu_hot_search()
        
        # 4. 获取东财内部排名股票
        dc_stocks = get_dongcai_ranking_stocks()
        
        # # 5. 获取股吧热门股票
        # guba_stocks = get_guba_hot_stocks()
        
        print("\n" + "="*60)
        print("数据整合与处理")
        print("="*60)
        
        # 收集所有格式化代码
        all_formatted_codes = []
        data_sources = {}  # 记录每个数据源的股票
        
        # 东方财富数据
        if not em_df.empty:
            em_formatted_codes = em_df['格式化代码'].dropna().tolist()
            all_formatted_codes.extend(em_formatted_codes)
            data_sources['东方财富热点排名'] = em_formatted_codes
        
        # 雪球数据
        if not xq_df.empty:
            xq_formatted_codes = xq_df['格式化代码'].dropna().tolist()
            all_formatted_codes.extend(xq_formatted_codes)
            data_sources['雪球热门关注'] = xq_formatted_codes
        
        # 百度热搜数据（没有标准代码，暂时跳过）
        if not baidu_df.empty:
            print("百度热搜数据没有标准股票代码，暂不处理")
        
        # 东财内部排名
        if dc_stocks:
            all_formatted_codes.extend(dc_stocks)
            data_sources['东财内部排名'] = dc_stocks
        
        
        # 去重并过滤
        all_formatted_codes = list(set(all_formatted_codes))
        all_formatted_codes = [code for code in all_formatted_codes if isinstance(code, str)]
        
        # 过滤掉688,300和.BJ结尾的股票
        filtered_codes = []
        for code in all_formatted_codes:
            if code:
                if not code.endswith('.BJ') and not code.startswith('688') and not code.startswith('30'):
                    filtered_codes.append(code)
        
        all_formatted_codes = filtered_codes
        
        # 过滤跌停股票
        all_formatted_codes = filter_limit_down_stocks(all_formatted_codes)
        
        print(f"总股票数量（去重后）: {len(all_formatted_codes)} 只")
        
        # 生成详细的数据来源信息
        source_info = []
        for source_name, stocks in data_sources.items():
            source_info.append(f"{source_name}: {len(stocks)} 只")
        
        print("各数据源股票数量:")
        for info in source_info:
            print(f"  {info}")
        
        # 输出到TXT文件
        txt_filename = f"all_hot_stocks_{date_str}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"# 多源热点股票数据\n")
            f.write(f"# 生成时间: {current_time}\n")
            f.write(f"# 代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}\n")
            f.write(f"# 总股票数量: {len(all_formatted_codes)} 只\n")
            f.write(f"# 数据来源: {', '.join(source_info)}\n\n")
            for code in all_formatted_codes:
                f.write(f"{code}\n")
        
        print(f"\n已生成股票代码文件: {txt_filename}")
        
        # 输出整合的Excel文件
        excel_filename = f"all_hot_stocks_detailed_{date_str}.xlsx"
        with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
            # 所有格式化代码汇总
            all_codes_df = pd.DataFrame({
                '股票代码': all_formatted_codes,
                '数据来源': [', '.join([s for s, lst in data_sources.items() if code in lst]) 
                          for code in all_formatted_codes]
            })
            all_codes_df.to_excel(writer, sheet_name='所有热门股票', index=False)
            
            # 东方财富数据
            if not em_df.empty:
                em_export_columns = ['当前排名', '代码', '格式化代码', '股票名称', '最新价', '涨跌幅', '涨跌额', '数据来源']
                em_export_columns = [col for col in em_export_columns if col in em_df.columns]
                em_df[em_export_columns].to_excel(writer, sheet_name='东方财富热点', index=False)
            
            # 雪球数据
            if not xq_df.empty:
                xq_export_columns = ['代码', '格式化代码', '股票名称', '最新价', '关注度', '数据来源']
                xq_export_columns = [col for col in xq_export_columns if col in xq_df.columns]
                xq_df[xq_export_columns].to_excel(writer, sheet_name='雪球热门关注', index=False)
        
        print(f"已生成详细Excel文件: {excel_filename}")
        
        # 数据预览
        print("\n" + "="*60)
        print("数据预览（前10只股票）")
        print("="*60)
        print("股票代码 | 数据来源")
        print("-" * 40)
        for i, code in enumerate(all_formatted_codes[:10], 1):
            sources = ', '.join([s for s, lst in data_sources.items() if code in lst])
            print(f"{code:15} | {sources}")
        
        # 保存到数据库
        print("\n" + "="*60)
        print("保存数据到数据库...")
        save_to_database(all_formatted_codes)
        
        print("\n" + "="*60)
        print("执行完成!")
        print(f"获取时间: {current_time}")
        print(f"代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}")
        print(f"总股票数量: {len(all_formatted_codes)} 只")
        print(f"数据文件: {txt_filename}")
        print(f"详细文件: {excel_filename}")
        print("="*60)
        
    except Exception as e:
        print(f"处理数据时发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()