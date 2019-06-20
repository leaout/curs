# -*- coding: utf-8 -*-

import six
import pickle

import numpy as np
from curs.log_handler.logger import logger

def iter_properties_of_class(cls):
    for varname in vars(cls):
        value = getattr(cls, varname)
        if isinstance(value, property):
            yield varname


def properties(inst):
    result = {}
    for cls in inst.__class__.mro():
        abandon_properties = getattr(cls, '__abandon_properties__', [])
        for varname in iter_properties_of_class(cls):
            if varname[0] == "_":
                continue
            if varname in abandon_properties:
                # 如果 设置了 __abandon_properties__ 属性，则过滤其中的property，不输出相关内容
                continue
            # FIXME: 这里getattr在iter_properties_of_class中掉用过了，性能比较差，可以优化
            tmp = getattr(inst, varname)
            if varname == "positions":
                tmp = list(tmp.keys())
            if hasattr(tmp, '__simple_object__'):
                result[varname] = tmp.__simple_object__()
            else:
                result[varname] = tmp
    return result

def property_repr(inst):
    # return pformat(properties(inst))
    return "%s(%s)" % (inst.__class__.__name__, properties(inst))

class RunInfo(object):
    """
    策略运行信息
    """
    __repr__ = property_repr

    def __init__(self, config):
        self._start_date = config.base.start_date
        self._end_date = config.base.end_date
        self._frequency = config.base.frequency
        # self._stock_starting_cash = config.base.accounts.get(DEFAULT_ACCOUNT_TYPE.STOCK.name, 0)
        # self._future_starting_cash = config.base.accounts.get(DEFAULT_ACCOUNT_TYPE.FUTURE.name, 0)
        self._benchmark = config.base.benchmark
        self._margin_multiplier = config.base.margin_multiplier
        self._run_type = config.base.run_type

        # For Mod

        # FIXME: deprecationwarning
        self._matching_type = None
        self._slippage = np.nan
        self._commission_multiplier = np.nan
        try:
            self._matching_type = config.mod.sys_simulation.matching_type
            self._slippage = config.mod.sys_simulation.slippage
            self._commission_multiplier = config.mod.sys_simulation.commission_multiplier
        except:
            pass

    @property
    def start_date(self):
        """
        [datetime.date] 策略的开始日期
        """
        return self._start_date

    @property
    def end_date(self):
        """
        [datetime.date] 策略的结束日期
        """
        return self._end_date

    @property
    def frequency(self):
        """
        [str] 策略频率，'1d'或'1m'
        """
        return self._frequency

    @property
    def stock_starting_cash(self):
        """
        [float] 股票账户初始资金
        """
        return self._stock_starting_cash

    @property
    def future_starting_cash(self):
        """
        [float] 期货账户初始资金
        """
        return self._future_starting_cash

    @property
    def slippage(self):
        """
        [float] 滑点水平
        """
        return self._slippage

    @property
    def benchmark(self):
        """
        [str] 基准合约代码
        """
        return self._benchmark

    @property
    def matching_type(self):
        """
        [str] 撮合方式
        """
        return self._matching_type

    @property
    def commission_multiplier(self):
        """
        [float] 手续费倍率
        """
        return self._commission_multiplier

    @property
    def margin_multiplier(self):
        """
        [float] 保证金倍率
        """
        return self._margin_multiplier

    @property
    def run_type(self):
        """
        [str] 运行类型
        """
        return self._run_type


class StrategyContext(object):
    def __repr__(self):
        items = ("%s = %r" % (k, v)
                 for k, v in six.iteritems(self.__dict__)
                 if not callable(v) and not k.startswith("_"))
        return "Context({%s})" % (', '.join(items),)

    def __init__(self):
        self._config = None

    def get_state(self):
        dict_data = {}
        for key, value in six.iteritems(self.__dict__):
            if key.startswith("_"):
                continue
            try:
                dict_data[key] = pickle.dumps(value)
            except Exception as e:
                logger.warn("context.{} can not pickle", key)
        return pickle.dumps(dict_data)

    def set_state(self, state):
        dict_data = pickle.loads(state)
        for key, value in six.iteritems(dict_data):
            try:
                self.__dict__[key] = pickle.loads(value)
                logger.debug("restore context.{} {}", key, type(self.__dict__[key]))
            except Exception as e:
                logger.warn('context.{} can not restore', key)

    @property
    def universe(self):
        """
        list[`str`]

        在运行 :func:`update_universe`, :func:`subscribe` 或者 :func:`unsubscribe` 的时候，合约池会被更新。

        需要注意，合约池内合约的交易时间（包含股票的策略默认会在股票交易时段触发）是handle_bar被触发的依据。
        """
        # return Environment.get_instance().get_universe()

    @property
    def now(self):
        """
        [datetime.datetime] 当前 Bar 所对应的时间
        """
        # return Environment.get_instance().calendar_dt

    @property
    def run_info(self):
        """
        [:class:`~RunInfo`] 运行信息
        """
        # config = Environment.get_instance().config
        # return RunInfo(config)

    @property
    def portfolio(self):
        """
        [:class:`~Portfolio`] 投资组合

        =========================   =========================   ==============================================================================
        属性                         类型                        注释
        =========================   =========================   ==============================================================================
        accounts                    dict                        账户字典
        start_date                  datetime.datetime           策略投资组合的回测/实时模拟交易的开始日期
        units                       float                       份额
        unit_net_value              float                       净值
        daily_pnl                   float                       当日盈亏，当日盈亏的加总
        daily_returns               float                       投资组合每日收益率
        total_returns               float                       投资组合总收益率
        annualized_returns          float                       投资组合的年化收益率
        total_value                 float                       投资组合总权益
        positions                   dict                        一个包含所有仓位的字典，以order_book_id作为键，position对象作为值
        cash                        float                       总的可用资金
        market_value                float                       投资组合当前的市场价值，为子组合市场价值的加总
        =========================   =========================   ==============================================================================

        """
        # return Environment.get_instance().portfolio

    @property
    def stock_account(self):
        # return self.portfolio.accounts[DEFAULT_ACCOUNT_TYPE.STOCK.name]
        raise NotImplementedError
    @property
    def future_account(self):
        # return self.portfolio.accounts[DEFAULT_ACCOUNT_TYPE.FUTURE.name]
        raise NotImplementedError
    @property
    def config(self):
        # return Environment.get_instance().config
        raise NotImplementedError

    @property
    def slippage(self):
        raise NotImplementedError

    @property
    def benchmark(self):
        raise NotImplementedError

    @property
    def margin_rate(self):
        raise NotImplementedError

    @property
    def commission(self):
        raise NotImplementedError

    @property
    def short_selling_allowed(self):
        raise NotImplementedError



def main():
    context = StrategyContext()
    context.s1=1
    print(context)

if __name__ == "__main__":
    main()