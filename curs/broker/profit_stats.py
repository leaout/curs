# coding: utf-8
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProfitStats:
    """
    盈利时间统计
    功能：
    1. 记录买入后每个时间点的盈亏
    2. 统计最大盈利出现的时间
    3. 统计平均成交时间
    4. 统计成交率
    """
    
    def __init__(self, data_dir: str = "data/strategy_records"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.stats_file = os.path.join(data_dir, "profit_stats.json")
        
        self.current_trades: Dict[str, Dict] = {}  # stock_code -> trade_info
        self.history_stats: List[Dict] = []
        
        self._load_history()
    
    def _load_history(self):
        """加载历史统计"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    self.history_stats = json.load(f)
                logger.info(f"已加载历史盈利统计 {len(self.history_stats)} 条")
            except Exception as e:
                logger.error(f"加载历史统计失败: {e}")
                self.history_stats = []
    
    def _save_history(self):
        """保存历史统计"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史统计失败: {e}")
    
    def record_buy(self, stock_code: str, order_id: str, price: float, 
                  volume: int, buy_time: datetime):
        """记录买入"""
        self.current_trades[stock_code] = {
            "order_id": order_id,
            "buy_price": price,
            "buy_volume": volume,
            "buy_time": buy_time.isoformat(),
            "buy_timestamp": buy_time.timestamp(),
            "filled": False,
            "price_points": [],  # [(timestamp, price), ...]
            "profit_points": []  # [(timestamp, profit_pct), ...]
        }
    
    def update_price(self, stock_code: str, current_price: float):
        """更新价格并记录盈亏曲线"""
        if stock_code not in self.current_trades:
            return
        
        trade = self.current_trades[stock_code]
        now = datetime.now()
        timestamp = now.timestamp()
        
        trade["price_points"].append({
            "timestamp": timestamp,
            "time": now.strftime("%H:%M:%S"),
            "price": current_price
        })
        
        if trade["filled"]:
            buy_price = trade["buy_price"]
            profit_pct = (current_price - buy_price) / buy_price * 100
            
            trade["profit_points"].append({
                "timestamp": timestamp,
                "time": now.strftime("%H:%M:%S"),
                "profit_pct": profit_pct,
                "current_price": current_price
            })
    
    def record_filled(self, stock_code: str, filled_price: float, filled_volume: int):
        """记录成交"""
        if stock_code not in self.current_trades:
            logger.warning(f"成交记录但未找到买入记录: {stock_code}")
            return
        
        trade = self.current_trades[stock_code]
        trade["filled"] = True
        trade["filled_price"] = filled_price
        trade["filled_volume"] = filled_volume
        trade["filled_time"] = datetime.now().isoformat()
        trade["filled_timestamp"] = datetime.now().timestamp()
        
        fill_time_seconds = trade["filled_timestamp"] - trade["buy_timestamp"]
        trade["wait_fill_seconds"] = fill_time_seconds
        
        logger.info(f"订单成交: {stock_code} - 买入价格: {trade['buy_price']}, 成交价格: {filled_price}, 等待时间: {fill_time_seconds:.1f}秒")
    
    def record_cancelled(self, stock_code: str, reason: str = "timeout"):
        """记录撤单"""
        if stock_code not in self.current_trades:
            return
        
        trade = self.current_trades[stock_code]
        trade["cancelled"] = True
        trade["cancelled_time"] = datetime.now().isoformat()
        trade["cancel_reason"] = reason
        
        self._save_trade_to_history(stock_code, trade)
        del self.current_trades[stock_code]
    
    def record_sell(self, stock_code: str, sell_price: float, sell_volume: int):
        """记录卖出"""
        if stock_code not in self.current_trades:
            return
        
        trade = self.current_trades[stock_code]
        trade["sell_price"] = sell_price
        trade["sell_volume"] = sell_volume
        trade["sell_time"] = datetime.now().isoformat()
        
        if trade.get("filled"):
            buy_price = trade["filled_price"]
            profit_pct = (sell_price - buy_price) / buy_price * 100
            trade["profit_pct"] = profit_pct
            
            sell_timestamp = datetime.now().timestamp()
            if "filled_timestamp" in trade:
                hold_seconds = sell_timestamp - trade["filled_timestamp"]
                trade["hold_seconds"] = hold_seconds
            
            logger.info(f"卖出完成: {stock_code} - 盈利: {profit_pct:.2f}%")
        
        self._save_trade_to_history(stock_code, trade)
        del self.current_trades[stock_code]
    
    def _save_trade_to_history(self, stock_code: str, trade: Dict):
        """保存交易到历史"""
        trade["stock_code"] = stock_code
        trade["record_time"] = datetime.now().isoformat()
        self.history_stats.append(trade)
        
        if len(self.history_stats) > 1000:
            self.history_stats = self.history_stats[-1000:]
        
        self._save_history()
    
    def get_profit_analysis(self) -> Dict:
        """获取盈利分析统计"""
        if not self.history_stats:
            return {}
        
        filled_trades = [t for t in self.history_stats if t.get("filled")]
        cancelled_trades = [t for t in self.history_stats if t.get("cancelled")]
        
        stats = {
            "total_trades": len(self.history_stats),
            "filled_count": len(filled_trades),
            "cancelled_count": len(cancelled_trades),
            "fill_rate": len(filled_trades) / len(self.history_stats) * 100 if self.history_stats else 0,
        }
        
        if filled_trades:
            profits = [t.get("profit_pct", 0) for t in filled_trades]
            stats["avg_profit_pct"] = sum(profits) / len(profits)
            stats["max_profit_pct"] = max(profits)
            stats["min_profit_pct"] = min(profits)
            stats["win_rate"] = len([p for p in profits if p > 0]) / len(profits) * 100
            
            wait_times = [t.get("wait_fill_seconds", 0) for t in filled_trades if t.get("wait_fill_seconds")]
            if wait_times:
                stats["avg_wait_fill_seconds"] = sum(wait_times) / len(wait_times)
                stats["max_wait_fill_seconds"] = max(wait_times)
            
            hold_times = [t.get("hold_seconds", 0) for t in filled_trades if t.get("hold_seconds")]
            if hold_times:
                stats["avg_hold_seconds"] = sum(hold_times) / len(hold_times)
                stats["max_hold_seconds"] = max(hold_times)
            
            stats["profit_to_max_time"] = self._calculate_profit_to_max_time(filled_trades)
        
        return stats
    
    def _calculate_profit_to_max_time(self, filled_trades: List[Dict]) -> Dict:
        """计算从买入到最大盈利的时间统计"""
        time_to_max_list = []
        
        for trade in filled_trades:
            if not trade.get("profit_points"):
                continue
            
            profit_points = trade["profit_points"]
            if not profit_points:
                continue
            
            buy_timestamp = trade.get("buy_timestamp", 0)
            if not buy_timestamp:
                continue
            
            max_profit = max(p["profit_pct"] for p in profit_points)
            max_point = next((p for p in profit_points if p["profit_pct"] == max_profit), None)
            
            if max_point and buy_timestamp > 0:
                time_to_max = max_point["timestamp"] - buy_timestamp
                time_to_max_list.append({
                    "stock_code": trade["stock_code"],
                    "max_profit_pct": max_profit,
                    "time_to_max_seconds": time_to_max,
                    "max_profit_time": max_point["time"]
                })
        
        if not time_to_max_list:
            return {}
        
        times = [t["time_to_max_seconds"] for t in time_to_max_list]
        
        return {
            "avg_time_to_max_seconds": sum(times) / len(times),
            "max_time_to_max_seconds": max(times),
            "min_time_to_max_seconds": min(times),
            "details": time_to_max_list
        }
    
    def get_pending_trades(self) -> List[Dict]:
        """获取当前待成交订单"""
        return [
            {
                "stock_code": code,
                "order_id": trade["order_id"],
                "buy_price": trade["buy_price"],
                "buy_time": trade["buy_time"],
                "wait_seconds": datetime.now().timestamp() - trade["buy_timestamp"]
            }
            for code, trade in self.current_trades.items()
            if not trade.get("filled")
        ]
    
    def get_profit_curve(self, stock_code: str) -> Optional[List[Dict]]:
        """获取指定股票的价格/盈亏曲线"""
        if stock_code not in self.current_trades:
            return None
        return self.current_trades[stock_code].get("profit_points", [])
    
    def get_summary_report(self) -> str:
        """生成汇总报告"""
        analysis = self.get_profit_analysis()
        
        if not analysis:
            return "暂无足够数据进行统计分析"
        
        lines = [
            "=" * 50,
            "交易统计分析报告",
            "=" * 50,
            f"总交易次数: {analysis.get('total_trades', 0)}",
            f"成交次数: {analysis.get('filled_count', 0)}",
            f"撤单次数: {analysis.get('cancelled_count', 0)}",
            f"成交率: {analysis.get('fill_rate', 0):.1f}%",
        ]
        
        if "avg_profit_pct" in analysis:
            lines.extend([
                "",
                "盈利统计:",
                f"  平均盈利: {analysis['avg_profit_pct']:.2f}%",
                f"  最大盈利: {analysis['max_profit_pct']:.2f}%",
                f"  最小盈利: {analysis['min_profit_pct']:.2f}%",
                f"  胜率: {analysis['win_rate']:.1f}%",
            ])
        
        if "avg_wait_fill_seconds" in analysis:
            lines.extend([
                "",
                "成交时间统计:",
                f"  平均等待成交: {analysis['avg_wait_fill_seconds']:.1f}秒",
                f"  最长等待成交: {analysis['max_wait_fill_seconds']:.1f}秒",
            ])
        
        if "avg_hold_seconds" in analysis:
            lines.extend([
                "",
                "持仓时间统计:",
                f"  平均持仓: {analysis['avg_hold_seconds']/60:.1f}分钟",
                f"  最长持仓: {analysis['max_hold_seconds']/60:.1f}分钟",
            ])
        
        if "profit_to_max_time" in analysis and analysis["profit_to_max_time"]:
            ptm = analysis["profit_to_max_time"]
            lines.extend([
                "",
                "最大盈利时间统计:",
                f"  平均达最大盈利时间: {ptm.get('avg_time_to_max_seconds', 0):.1f}秒",
                f"  最快达最大盈利: {ptm.get('min_time_to_max_seconds', 0):.1f}秒",
                f"  最慢达最大盈利: {ptm.get('max_time_to_max_seconds', 0):.1f}秒",
            ])
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


def load_profit_stats(data_dir: str = "data/strategy_records") -> ProfitStats:
    """加载盈利统计实例"""
    return ProfitStats(data_dir)
