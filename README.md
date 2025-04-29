# curs
Curs is an personal automated quantitative investment platform.
## Strategy
```mermaid
graph TD
    A[实时Tick数据] --> B{多层过滤}
    B -->|ST/新股/昨日涨停| C[排除]
    B -->|通过初筛| D[核心指标计算]
    D --> E[封单强度>0.5%?]
    D --> F[挂单减少速度>500手/s?]
    D --> G[市场热度>30涨停?]
    E & F & G --> H{买入信号}
    H -->|Yes| I[动态仓位计算]
    I --> J[执行买入]
    J --> K[持续监控]
    K --> L{卖出条件}
    L -->|动态止盈| M[回落2%卖出]
    L -->|均线跌破| N[破5日线卖出]
    L -->|尾盘强制| O[14:55清仓]
```
## Install
python 3.10 recommended!
```bash
pip install -r requirements.txt
```
```bash
python setup.py install 
```


## Module

collection   数据采集

data_source   历史数据

log_handler   日志

real_quote    实时行情

utils		公共包

strategy_loader   策略热加载

main			主程序逻辑  
## Back trader 

## 交易接口接入
- miniqmt

## todolist
- 数据存储改为postgresql
- 新增统计策略，统计当天涨停，跌停，涨停炸板
