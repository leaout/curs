# 热点股研究台

## 查看个股报告

打开[热点股研究台](http://127.0.0.1:5000/finance-board)，先选报告日期，再点左侧股票名称或代码。右侧会同时切换到该股的报告和报告引用的来源。点击「全部股票」可查看该日期的所有报告和来源。切换股票会保留所选日期。

页面默认显示北京时间当天。若显示「该股票在所选日期暂无报告」，可切换到其他日期，或在下方发起个股分析。定时批次跨过午夜时，报告仍归到批次的计划日期。左侧股票列表以最近一个有热点榜记录的交易日为准，所选日期有报告的股票也会出现在列表里。

## 手动调用 WorkBuddy

1. 保持 Windows 桌面版 WorkBuddy 已登录并运行。若「检查连接」提示找不到本地管道，先在 WorkBuddy 内发送一条消息，再检查一次。
2. 点击左侧股票会自动填入分析框，也可以手动输入代码，例如 `002185.SZ`。点击「分析个股」提交。点击「分析整个热点池」会按最新热点榜逐只分析，最多 100 只。
3. Curs 向 WorkBuddy 发送「请实时分析一下这只股票：【股票代码】」，由智能体决定分析内容。收到格式有效且带有引用来源的报告后，Curs 会立即保存。页面显示成功数量和逐股失败原因。

## 每日定时分析

Curs 引擎每天北京时间 **21:30** 启动批次，并保存批次名单。定时任务每 15 分钟检查是否有未完成的股票，在当天 21:00 至 21:30 的换榜窗口暂停补跑。服务重启后，补跑会沿用已保存的名单与进度。每只股票在同一批次内最多自动尝试三次。

每个批次日期先生成一份独立的 A 股市场情绪报告，列出主要指数、上涨／下跌／平盘家数及市场成交额。休市日标注引用的最近交易日。在[市场页](http://127.0.0.1:5000/market-sentiment#market-close)的「收盘报告」区按日期查看。市场报告最多自动尝试三次，保存成功后该日期不会再生成。市场报告失败时，个股分析继续执行。

「定时分析已生成」显示所选批次已完成的报告数和该批次的股票总数。手动分析的报告也可以按日期查看。定时运行需要 Curs 引擎和已登录的 WorkBuddy 桌面版保持运行。

## 部署与数据

Curs 使用 [Desktop Bridge](https://github.com/gosick233-cloud/Codex-WorkBuddy-Desktop-Bridge) 的 ACP 客户端，固定版本为 `c00a8e5eab809a97963277e71ec008abb3d372ae`。桥接仓库位于 `.venv/workbuddy-desktop-bridge`，Python 环境需安装 `httpx>=0.27,<1`。每次调用创建临时会话，仅允许 WebSearch。WorkBuddy 更新后，可以先跑一只股票确认能生成报告。页面的「检查连接」只检查本地管道，实际分析成功才确认整条链路可用。

新环境按项目 README 建好 `.venv` 后，在项目根目录运行以下命令：

```powershell
git clone https://github.com/gosick233-cloud/Codex-WorkBuddy-Desktop-Bridge.git .venv/workbuddy-desktop-bridge
git -C .venv/workbuddy-desktop-bridge checkout --detach c00a8e5eab809a97963277e71ec008abb3d372ae
.\.venv\Scripts\python.exe -m pip install 'httpx>=0.27,<1'
```

研究报告、来源和定时批次进度保存在 `data/stock_intel.sqlite3`。可用 `python -m curs.stock_intel --import-agent-report 文件路径` 导入历史报告，其中 `source_ids` 必须对应数据库内同一股票的来源。
