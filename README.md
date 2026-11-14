# Curs

### A 股热点研究与策略信号观察台

把市场热点、公开行情、策略信号与智能体研究放在一个工作台中，帮助你更连贯地观察每天的市场变化。

**当前版本：仅研究与信号记录，不连接实盘账户、不自动下单。**

[English](README_EN.md) · [开始使用](#quick-start) · [项目文档](#项目文档)

## 主要功能

### 热点追踪

汇总 WhatsHot 展示的同花顺热股榜，查看热点股票、数据来源与采集时间，并保留每日快照供后续研究。

### 策略信号观察

结合公开行情运行现有 A 股策略，集中查看信号、触发依据和后续行情变化。信号用于观察与研究，不等于实际委托或成交。

### 市场情绪与涨停梯队

通过全市场涨跌、涨停记录和连板梯队，观察市场环境、热点延续和接力状态。

### 智能体个股研究

从热点股票进入个股研究，可按需调用本机 WorkBuddy Desktop Bridge 汇总分析结果。

## Quick Start

需要 Python 3.10+、PostgreSQL 和可启动的 Chrome。

```powershell
git clone https://github.com/leaout/curs.git
cd curs
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在项目根目录创建 `config.local.yml`，填入自己的数据库连接信息：

```yaml
database:
  host: 127.0.0.1
  port: 5432
  database: postgres
  user: postgres
  password: "你的数据库密码"
```

启动服务并打开 <http://localhost:5000>：

```powershell
python run.py
```

若服务账户无法自动找到 Chrome，可在同一配置文件中添加 `whatshot.chrome_path`。完整部署和故障排查见[WhatsHot 接入说明](docs/WHATSHOT_INTEGRATION.md)与[信号模式指南](docs/SIGNAL_ONLY.md)。

## 项目文档

- [热点股票智能体研究](docs/STOCK_INTELLIGENCE.md)
- [WhatsHot 热股榜接入](docs/WHATSHOT_INTEGRATION.md)
- [信号模式、行情与部署](docs/SIGNAL_ONLY.md)
- [连板接力观察](docs/RELAY_V1.md)
- [KOL 证据接入规则](docs/KOL_RELAY.md)
- [信号机会统计口径](docs/OPPORTUNITIES.md)

## 数据与使用边界

行情与热点来自公开数据源，来源或页面变化可能影响数据完整性。策略信号和智能体分析用于研究，不构成投资建议，也不能保证收益。当前项目不执行实盘交易。
