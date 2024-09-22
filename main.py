# coding: utf-8
import imp
from curs.real_quote.quote_engine import QuoteEngine
from curs.utils.config import load_yaml
from curs.cursglobal import *
from curs.strategy import *

import imaplib
import email
from email.header import decode_header
import requests
from pathlib import Path
import os
import re
project_dir = Path(__file__).resolve().parent

def download_file(url, target_directory=f"{project_dir}\\down"):
    # 构造目标文件路径
    file_name = url.split('=')[-1]
    target_path = os.path.join(target_directory, file_name)
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        os.makedirs(target_directory, exist_ok=True)
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"文件已成功下载到 {target_path}")
    else:
        print(f"下载失败，状态码：{response.status_code}")
        
def receive_email():
    # 连接到163邮箱的IMAP服务器
    username = 'leaout@163.com'  # 替换为你的163邮箱地址
    password = 'PQhub4wdpAPJmTtE'         # 替换为你的邮箱密码

    # 创建IMAP对象并登录
    imap_client = imaplib.IMAP4_SSL('imap.163.com')
    imap_client.login(username, password)

    # 解决网易邮箱报错：Unsafe Login. Please contact kefu@188.com for help
    imaplib.Commands["ID"] = ('AUTH',)
    args = ("name", username, "contact", username, "version", "1.0.0", "vendor", "myclient")
    imap_client._simple_command("ID", str(args).replace(",", "").replace("\'", "\""))
    mail_dir = imap_client.list()

    # 获取邮箱目录。INBOX(收件箱)/Drafts(草稿箱)/Junk(垃圾箱)/Trash(已删除)/Sent Messages(已发送)
    # 选择邮箱。返回的数据是中的消息数 信箱 (EXISTS 反应）。默认值信箱是'INBOX'
    # 选择收件箱
    imap_client.select('inbox')

    # 搜索所有邮件
    # 在邮箱中搜索邮件。ALL(全部邮件),UNSEEN(未读邮件),SEEN(已读邮件)
    # status：搜索结果状态
    # messages：邮件的索引号
    status, messages = imap_client.search(None, 'ALL')
    mail_ids = messages[0].split()

    # 解析最后一封邮件
    if mail_ids:
        latest_email_id = mail_ids[-1]
        
        # 获取邮件
        status, msg_data = imap_client.fetch(latest_email_id, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])

        # 解码邮件主题
        subject, encoding = decode_header(msg['Subject'])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else 'utf-8')

        print('邮件主题:', subject)

        # 获取邮件内容
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':  # 获取纯文本部分
                    body = part.get_payload(decode=True).decode('utf-8')
                    print('邮件内容:', body)
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8')
            print('邮件内容:', body)
            ret = re.search(r'下载链接：(.*\.csv)', body)
            down_link = ret.group(1)
            # print(down_link)
            download_file(down_link)

    # 登出
    imap_client.logout()

def main():
    #event
    event_bus = EventBus()
    event_bus.start()

    engine = QuoteEngine(event_bus, CursGlobal.get_instance())
    engine.start()

    while 1 :
        time.sleep(3)
    pass


def load_strategy(strategy_path, event_bus):
    s_loader = FileStrategyLoader(strategy_path)
    scop = {}
    s_loader.load(scop)
    strategy_context = StrategyContext()
    strategy = Strategy(event_bus, scop, strategy_context)
    strategy.init()


if __name__ == "__main__":
    main()