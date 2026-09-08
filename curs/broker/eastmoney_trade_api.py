"""
东方财富证券交易 API — 单文件完整实现
========================================
依赖: pip install requests pycryptodome ddddocr pillow

用法:
    from eastmoney_trade_api import EastMoneyTradeAPI

    api = EastMoneyTradeAPI()
    api.login(account_no="540630xxxxxx", password="123456")

    balance = api.get_balance()
    positions = api.get_positions()
    api.buy("000001", price=12.50, amount=100)
    api.sell("000001", price=13.00, amount=100)
    api.cancel_entrust("25405")

    today_orders = api.get_today_entrusts()
    today_deals = api.get_today_deals()
    history = api.get_his_entrusts("20260601", "20260622")
    history_deals = api.get_his_deals("20260601", "20260622")
    funds_flow = api.get_funds_flow("2026-06-01", "2026-06-22")

    api.logout()
"""

import base64
import json
import os
import pickle
import random
import re
import time
import uuid
from typing import Optional

import requests
import ddddocr
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDHdsyxT66pDG4p73yope7jxA92
c0AT4qIJ/xtbBcHkFPK77upnsfDTJiVEuQDH+MiMeb+XhCLNKZGp0yaUU6GlxZdp
+nLW8b7Kmijr3iepaDhcbVTsYBWchaWUXauj9Lrhz58/6AE/NF0aMolxIGpsi+ST
2hSHPu3GSXMdhPCkWQIDAQAB
-----END PUBLIC KEY-----"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Host": "jywg.18.cn",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Referer": "https://jywg.18.cn/Login?el=1&clear=1",
    "X-Requested-With": "XMLHttpRequest",
}


def _encrypt_password(pwd: str) -> str:
    """RSA 加密密码"""
    rsakey = RSA.importKey(RSA_PUBLIC_KEY)
    cipher = Cipher_pkcs1_v1_5.new(rsakey)
    return base64.b64encode(cipher.encrypt(pwd.encode("utf-8"))).decode("utf-8")


def _format_time(time_str) -> str:
    """解析 API 返回的时间字符串 → HH:mm:ss"""
    if not time_str or not str(time_str).strip():
        return ""
    t = str(time_str).strip()
    if ":" in t and len(t) <= 8:
        return t
    if t.isdigit():
        if len(t) == 14:
            t = t[-6:]
        elif len(t) >= 13:
            try:
                return time.strftime("%H:%M:%S", time.localtime(int(t) / 1000))
            except Exception:
                pass
        elif len(t) == 10:
            try:
                return time.strftime("%H:%M:%S", time.localtime(int(t)))
            except Exception:
                pass
        if len(t) >= 6:
            if len(t) >= 14:
                t = t[8:]
            s = t[:6]
            return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    return t


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


# ═══════════════════════════════════════════════════════════════
# API 类
# ═══════════════════════════════════════════════════════════════

class EastMoneyTradeAPI:
    """东方财富证券交易 API 客户端"""

    def __init__(self, session_file: str = "eastmoney_trader.session"):
        self.session_file = session_file
        self.validate_key: Optional[str] = None
        self.account_no: str = ""
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(HEADERS)
        self._ocr = ddddocr.DdddOcr()

        # 尝试从缓存恢复
        self._reload_session()

    # ─── Session 持久化 ──────────────────────────────────

    def _save_session(self):
        with open(self.session_file, "wb") as f:
            pickle.dump((self.validate_key, self.session), f)

    def _reload_session(self) -> bool:
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "rb") as f:
                    self.validate_key, self.session = pickle.load(f)
                return True
            except Exception:
                pass
        return False

    def _get_url(self, path: str) -> str:
        return f"https://jywg.18.cn/{path}?validatekey={self.validate_key}"

    # ─── 登录 ──────────────────────────────────────────

    def _recognize_captcha(self) -> str:
        rand = f"0.305{random.randint(100000, 900000)}"
        resp = self.session.get(f"https://jywg.18.cn/Login/YZM?randNum={rand}")
        code = self._ocr.classification(resp.content)
        if len(code) == 4:
            return code
        time.sleep(1)
        return self._recognize_captcha()

    def login(self, account_no: str, password: str) -> dict:
        """
        登录东方财富证券账户
        成功返回 {"success": True}
        """
        # 检查缓存会话是否有效
        if self.validate_key:
            try:
                self._heartbeat()
                self.account_no = account_no
                return {"success": True, "cached": True}
            except Exception:
                self.validate_key = None

        self.account_no = account_no

        for retry in range(5):
            captcha = self._recognize_captcha()
            enc_pwd = _encrypt_password(password)
            self.session.headers.update({
                "gw_reqtimestamp": str(int(round(time.time() * 1000))),
                "content-type": "application/x-www-form-urlencoded",
            })
            resp = self.session.post(
                "https://jywg.18.cn/Login/Authentication?validatekey=",
                data={
                    "duration": 1800,
                    "password": enc_pwd,
                    "identifyCode": captcha,
                    "type": "Z",
                    "userId": account_no,
                    "randNumber": f"0.9033461201665647898",
                    "authCode": "",
                    "secInfo": "",
                },
            ).json()

            status = resp.get("Status")
            if status == 0 or str(status) == "0":
                self._fetch_validate_key()
                self._save_session()
                return {"success": True}

            retry_count = retry + 1
            msg = resp.get("Message", "")
            print(f"[EastMoney] 登录失败 ({retry_count}/5): {msg}")

            if status is not None and (str(status) == "-1" or (isinstance(status, int) and status < 0)):
                raise Exception(f"登录失败: {msg}" if msg else "账号或密码错误")

            time.sleep(3)

        raise Exception(f"登录失败（已重试5次）")

    def _fetch_validate_key(self):
        resp = self.session.get("https://jywg.18.cn/Trade/Buy").text
        key_str = 'input id="em_validatekey" type="hidden" value="'
        begin = resp.index(key_str) + len(key_str)
        end = resp.index('" />', begin)
        self.validate_key = resp[begin:end]

    def _heartbeat(self):
        url = self._get_url("Com/queryAssetAndPositionV1")
        resp = self.session.post(url, data={"moneyType": "RMB"}).json()
        if resp.get("Status") != 0:
            raise Exception("心跳失败")

    def logout(self):
        """退出登录，清除缓存"""
        self.validate_key = None
        self.session.close()
        if os.path.exists(self.session_file):
            os.remove(self.session_file)

    # ─── 账户 ──────────────────────────────────────────

    def get_balance(self) -> dict:
        """获取账户资金"""
        url = self._get_url("Com/queryAssetAndPositionV1")
        data = self.session.post(url, data={"moneyType": "RMB"}).json()
        if data.get("Status") != 0:
            raise Exception("获取资金失败")
        asset = data["Data"][0]
        return {
            "asset_balance": _safe_float(asset.get("Zzc")),
            "current_balance": _safe_float(asset.get("Kqzj")),
            "enable_balance": _safe_float(asset.get("Kyzj")),
            "frozen_balance": _safe_float(asset.get("Djzj")),
            "market_value": _safe_float(asset.get("Zxsz")),
        }

    # ─── 持仓 ──────────────────────────────────────────

    def get_positions(self) -> list:
        """获取持仓（含当日盈亏 Dryk / Drykbl）"""
        url = self._get_url("Com/queryAssetAndPositionV1")
        data = self.session.post(url, data={"moneyType": "RMB"}).json()
        if data.get("Status") != 0:
            raise Exception("获取持仓失败")

        positions = data["Data"][0].get("positions", [])
        result = []
        for p in positions:
            zqsl = _safe_int(p.get("Zqsl"))
            zxjg = _safe_float(p.get("Zxjg"))
            result.append({
                "stock_code": p.get("Zqdm", ""),
                "stock_name": p.get("Zqmc", ""),
                "current_amount": zqsl,
                "enable_amount": _safe_int(p.get("Kysl")),
                "cost_price": _safe_float(p.get("Cbjg")),
                "last_price": zxjg,
                "market_value": _safe_float(p.get("Zxsz")) or (zxjg * zqsl),
                "income_balance": _safe_float(p.get("Ljyk")),
                "daily_pl": _safe_float(p.get("Dryk")),
                "daily_pl_pct": _safe_float(p.get("Drykbl")) * 100,
            })
        return result

    # ─── 当日委托 ──────────────────────────────────────

    def get_today_entrusts(self) -> list:
        """获取当日委托"""
        url = self._get_url("Search/GetOrdersData")
        data = self.session.get(url).json()
        if data.get("Status") != 0:
            raise Exception("获取委托失败")
        result = []
        for item in data.get("Data", []):
            time_field = item.get("Wtsj") or item.get("Bpsj") or ""
            result.append({
                "entrust_no": str(item.get("Wtbh", "")),
                "stock_code": str(item.get("Zqdm", "")),
                "stock_name": str(item.get("Zqmc", "")),
                "bs_type": str(item.get("Mmlb", "")),
                "entrust_price": _safe_float(item.get("Wtjg")),
                "entrust_amount": _safe_int(item.get("Wtsl")),
                "entrust_status": str(item.get("Wtzt", "")),
                "report_time": _format_time(time_field),
            })
        return result

    # ─── 当日成交 ──────────────────────────────────────

    def get_today_deals(self) -> list:
        """获取当日成交"""
        url = self._get_url("Search/GetDealData")
        data = self.session.get(url).json()
        if data.get("Status") != 0:
            raise Exception("获取成交失败")
        result = []
        for item in data.get("Data", []):
            result.append({
                "deal_no": str(item.get("Cjbh", "")),
                "entrust_no": str(item.get("Wtbh", "")),
                "stock_code": str(item.get("Zqdm", "")),
                "stock_name": str(item.get("Zqmc", "")),
                "bs_type": str(item.get("Mmlb", "")),
                "deal_price": _safe_float(item.get("Cjjg")),
                "deal_amount": _safe_int(item.get("Cjsl")),
                "entrust_price": _safe_float(item.get("Wtjg")),
                "deal_time": _format_time(item.get("Cjsj") or ""),
            })
        return result

    # ─── 买卖 ──────────────────────────────────────────

    def buy(self, stock_code: str, price: float, amount: int) -> dict:
        """买入股票"""
        url = self._get_url("Trade/SubmitTradeV2")
        resp = self.session.post(url, data={
            "stockCode": str(stock_code),
            "price": str(price),
            "amount": str(amount),
            "zqmc": "",
            "tradeType": "B",
        }).json()
        if resp.get("Status") != 0:
            raise Exception(f"买入失败: {resp.get('Message', resp)}")
        return {"success": True, "message": f"买入委托已提交: {stock_code} {price}×{amount}股"}

    def sell(self, stock_code: str, price: float, amount: int) -> dict:
        """卖出股票"""
        url = self._get_url("Trade/SubmitTradeV2")
        resp = self.session.post(url, data={
            "stockCode": str(stock_code),
            "price": str(price),
            "amount": str(amount),
            "zqmc": "",
            "tradeType": "S",
        }).json()
        if resp.get("Status") != 0:
            raise Exception(f"卖出失败: {resp.get('Message', resp)}")
        return {"success": True, "message": f"卖出委托已提交: {stock_code} {price}×{amount}股"}

    def cancel_entrust(self, entrust_no: str) -> dict:
        """撤销委托"""
        all_orders = self.get_today_entrusts()
        order = None
        for o in all_orders:
            if o["entrust_no"] == str(entrust_no):
                order = o
                break

        if not order:
            raise Exception(f"未找到委托 {entrust_no}")

        code = order["stock_code"]
        if code.startswith(("60", "68")):
            market = "HA"
        elif code.startswith(("00", "30")):
            market = "SA"
        else:
            market = "SA"
        mmlb = f"0{order['bs_type']}"
        wtrq = time.strftime("%Y%m%d")

        self.session.headers.update({
            "gw_reqtimestamp": str(int(round(time.time() * 1000))),
            "Referer": "https://jywg.18.cn/Trade/Revoke",
        })

        url = self._get_url("Trade/cancelStockWEB")
        for retry in range(3):
            resp = self.session.post(url, data={
                "wtrq": wtrq,
                "wtbh": str(entrust_no),
                "market": market,
                "mmlb": mmlb,
            }).json()
            if resp.get("Status") == 0:
                return {"success": True, "message": f"撤单已提交: {entrust_no}"}
            msg = resp.get("Message", "")
            if "网络繁忙" in str(msg) and retry < 2:
                time.sleep(2)
                continue
            raise Exception(f"撤单失败: {msg}" if msg else f"撤单失败: {entrust_no}")

        raise Exception(f"撤单失败: {entrust_no}")

    # ─── 历史委托 ──────────────────────────────────────

    def get_his_entrusts(self, start_date: str, end_date: str, count: int = 100) -> list:
        """
        历史委托
        start_date/end_date: YYYYMMDD 格式
        """
        self.session.headers.update({
            "gw_reqtimestamp": str(int(round(time.time() * 1000))),
            "Referer": "https://jywg.18.cn/Search/HisOrders",
        })
        url = self._get_url("Search/queryHisOrderMergeWEB")
        resp = self.session.post(url, data={
            "strdate": start_date, "enddate": end_date,
            "count": str(count), "poststr": "",
        }).json()
        if resp.get("Status") != 0:
            raise Exception(f"查询历史委托失败: {resp.get('Message')}")

        result = []
        for item in resp.get("Data", []):
            op_time = _format_time(str(item.get("opertime", "")))
            order_date = str(item.get("orderdate", ""))
            report_time = f"{order_date[:4]}-{order_date[4:6]}-{order_date[6:8]} {op_time}" if order_date else ""
            result.append({
                "entrust_no": str(item.get("ordersno", "")),
                "stock_code": str(item.get("stkcode", "")),
                "stock_name": str(item.get("stkname", "")),
                "bs_type": str(item.get("bsflag_color", "")),
                "bs_name": str(item.get("bsflag_ex", "")),
                "entrust_price": _safe_float(item.get("orderprice")),
                "entrust_amount": _safe_int(item.get("orderqty")),
                "deal_price": _safe_float(item.get("matchprice")),
                "deal_amount": _safe_int(item.get("matchqty")),
                "deal_money": _safe_float(item.get("matchamt")),
                "cancel_amount": _safe_int(item.get("cancelqty")),
                "entrust_status": str(item.get("orderstatus_ex", "")),
                "report_time": report_time,
                "market": str(item.get("market_ex", "")),
                "remark": str(item.get("remark", "")),
            })
        return result

    # ─── 历史成交 ──────────────────────────────────────

    def get_his_deals(self, start_date: str, end_date: str, count: int = 100) -> list:
        """历史成交"""
        self.session.headers.update({
            "gw_reqtimestamp": str(int(round(time.time() * 1000))),
            "Referer": "https://jywg.18.cn/Search/HisDeal",
        })
        url = self._get_url("Search/queryHisMatchMergeWEB")
        resp = self.session.post(url, data={
            "strdate": start_date, "enddate": end_date,
            "count": str(count), "poststr": "",
        }).json()
        if resp.get("Status") != 0:
            raise Exception(f"查询历史成交失败: {resp.get('Message')}")

        result = []
        for item in resp.get("Data", []):
            bizdate = str(item.get("bizdate", ""))
            matchtime = _format_time(str(item.get("matchtime", "")))
            report_time = f"{bizdate[:4]}-{bizdate[4:6]}-{bizdate[6:8]} {matchtime}" if bizdate else ""
            result.append({
                "bizdate": bizdate,
                "match_time": report_time,
                "stock_code": str(item.get("stkcode", "")),
                "stock_name": str(item.get("stkname", "")),
                "bs_name": str(item.get("bsflag_ex", "")),
                "bs_type": str(item.get("bsflag_color", "")),
                "order_price": _safe_float(item.get("orderprice")),
                "order_qty": _safe_int(item.get("orderqty")),
                "match_price": _safe_float(item.get("matchprice")),
                "match_qty": _safe_int(item.get("matchqty")),
                "match_amt": _safe_float(item.get("matchamt")),
                "fee_sxf": _safe_float(item.get("fee_sxf")),
                "fee_yhs": _safe_float(item.get("fee_yhs")),
                "fee_ghf": _safe_float(item.get("fee_ghf")),
                "fee_jsxf": _safe_float(item.get("fee_jsxf")),
                "fee_total": (_safe_float(item.get("fee_sxf")) + _safe_float(item.get("fee_yhs"))
                            + _safe_float(item.get("fee_ghf")) + _safe_float(item.get("fee_jsxf"))),
                "fund_effect": _safe_float(item.get("fundeffect")),
                "stk_balance": _safe_int(item.get("stkbal")),
                "fund_balance": _safe_float(item.get("fundbal")),
                "entrust_no": str(item.get("ordersno", "")),
                "market": str(item.get("market_ex", "")),
            })
        return result

    # ─── 交割单（资金流水）──────────────────────────────

    def get_funds_flow(self, start_date: str, end_date: str, count: int = 100) -> list:
        """
        交割单
        start_date/end_date: YYYY-MM-DD 格式
        """
        self.session.headers.update({
            "gw_reqtimestamp": str(int(round(time.time() * 1000))),
            "Referer": "https://jywg.18.cn/Search/FundsFlow",
        })
        url = self._get_url("Search/GetFundsFlow")
        resp = self.session.post(url, data={
            "st": start_date, "et": end_date,
            "qqhs": str(count), "dwc": "",
        }).json()
        if resp.get("Status") != 0:
            raise Exception(f"查询交割单失败: {resp.get('Message')}")

        result = []
        for item in resp.get("Data", []):
            fsrq = str(item.get("Fsrq", ""))
            fssj = _format_time(str(item.get("Fssj", "")))
            report_time = f"{fsrq[:4]}-{fsrq[4:6]}-{fsrq[6:8]} {fssj}" if fsrq else ""
            result.append({
                "bizdate": fsrq,
                "biz_time": report_time,
                "stock_code": str(item.get("Zqdm", "")),
                "stock_name": str(item.get("Zqmc", "")),
                "biz_name": str(item.get("Ywsm", "")),
                "match_qty": _safe_int(item.get("Cjsl")),
                "match_price": _safe_float(item.get("Cjjg")),
                "match_amt": _safe_float(item.get("Cjje")),
                "fee_sxf": _safe_float(item.get("Sxf")),
                "fee_yhs": _safe_float(item.get("Yhs")),
                "fee_ghf": _safe_float(item.get("Ghf")),
                "fee_jsxf": _safe_float(item.get("Jsxf")),
                "fee_jygf": _safe_float(item.get("Jygf")),
                "fee_total": (_safe_float(item.get("Sxf")) + _safe_float(item.get("Yhs"))
                            + _safe_float(item.get("Ghf")) + _safe_float(item.get("Jsxf"))
                            + _safe_float(item.get("Jygf"))),
                "fund_effect": _safe_float(item.get("Fsje")),
                "fund_balance": _safe_float(item.get("Zjye")),
                "stk_balance": _safe_int(item.get("Gfye") or item.get("Gpye")),
                "match_code": str(item.get("Cjbh", "")),
                "entrust_no": str(item.get("Htbh", "")),
                "market": str(item.get("Market", "")),
            })
        return result


# ═══════════════════════════════════════════════════════════════
# 使用示例
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    api = EastMoneyTradeAPI(session_file="my_trader.session")

    # 登录
    api.login(account_no="540630xxxxxx", password="your_trade_password")

    # 查询
    balance = api.get_balance()
    print("资金:", json.dumps(balance, ensure_ascii=False, indent=2))

    positions = api.get_positions()
    print("持仓:", json.dumps(positions, ensure_ascii=False, indent=2))

    today_orders = api.get_today_entrusts()
    print("当日委托:", json.dumps(today_orders, ensure_ascii=False, indent=2))

    # 交易
    # api.buy("000001", price=12.50, amount=100)
    # api.sell("000001", price=13.00, amount=100)
    # api.cancel_entrust("25405")

    # 历史
    # history = api.get_his_entrusts("20260601", "20260622")
    # history_deals = api.get_his_deals("20260601", "20260622")
    # funds = api.get_funds_flow("2026-06-01", "2026-06-22")

    api.logout()
