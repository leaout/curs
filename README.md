# Curs

Curs 是一个面向 A 股的个人量化研究与信号记录平台。当前默认运行在**仅记录信号**模式，不连接实盘账户、不自动下单。

[English Version](README_EN.md)

## 当前功能

- 使用腾讯公开行情，为现有策略生成并记录观察信号。
- 采集 WhatsHot 网页上的同花顺热股榜，股票池页面标明来源与采集时间。
- 保存每日热股快照和收盘涨停数据，供市场情绪与历史研究页面使用。
- 支持热点股票研究、WorkBuddy Desktop Bridge 分析、市场情绪观察、信号前向观察与连板接力影子观察。

## 热股榜采集

Curs 服务直接用本机 Chrome 渲染 WhatsHot 的公开同花顺热股榜页面，不需要 API Key，也不直接请求同花顺上游。工作日北京时间 15:35 后由 Web 服务自动同步，失败后每 15 分钟重试，最晚重试到 22:00；也可在“管理 → 股票池”手动同步。GitHub Actions 每日采集和归档导入流程已移除。

采集依赖运行服务的计算机安装 Chrome，且运行 Curs 的 Windows 账户可以启动它。无法自动发现 Chrome 时，可在 `config.local.yml` 设置：

```yaml
whatshot:
  chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

榜单不可访问、页面结构变化或未解析到有效股票时，服务会记录错误并重试，不会把旧缓存当成当天榜单。网页不提供可靠的实时成交价；来源、采集时间和数据限制见[热股榜接入说明](docs/WHATSHOT_INTEGRATION.md)。

## 安装与启动

需要 Python 3.10+、可访问的 PostgreSQL 数据库和 Chrome。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

默认访问 <http://localhost:5000>。日常热股自动同步由 Web 服务启动；若只启动引擎（`--engine-only`），不会运行该同步器。`--web-only` 可以运行页面和热股同步。

## 配置

数据库及本机路径等设置放在不纳入版本控制的 `config.local.yml`。`config.yml` 已包含默认行情和 WhatsHot 设置。至少配置数据库连接：

```yaml
database:
  host: 127.0.0.1
  port: 5432
  database: postgres
  user: postgres
  password: "change-me"
```

确保 PostgreSQL 可连接并已创建项目所需表。服务日志写入 `logs/`。切勿提交数据库密码、账户凭据、登录会话或本机运行数据。

## 运行边界

- `signal_only: true`、`broker: signal` 是当前默认配置；信号不代表订单或实际成交。
- 行情和 WhatsHot 网页均为外部公开来源，不提供服务可用性保证；页面或访问策略变化可能中断采集。
- 收盘任务依赖服务在采集时段持续运行；若主机休眠或服务停止，期间不会执行采集。
- WorkBuddy 分析需要本机 Desktop Bridge 已启动并可连接；这是可选分析能力，不影响热股榜同步。

## 设计与操作文档

- [WhatsHot 热股榜接入与排错](docs/WHATSHOT_INTEGRATION.md)
- [热点股票智能体研究](docs/STOCK_INTELLIGENCE.md)
- [仅信号模式、行情与部署](docs/SIGNAL_ONLY.md)
- [连板接力观察](docs/RELAY_V1.md)
- [KOL 证据接入规则](docs/KOL_RELAY.md)
- [信号机会统计口径](docs/OPPORTUNITIES.md)
- [代码审查记录](docs/REVIEW_20261014.md)
