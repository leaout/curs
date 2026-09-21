# Curs Vibe Trading

[English Version](README_EN.md) | 中文版

Curs 正在重构为一个面向多市场的 Trading Agent：每个策略都是一个长期大模型对话 Session，用户通过聊天创建和修改策略，交易信号、模型决策、风控与订单事件叠加在 K 线和时间线上。

旧 Flask 页面、`run.py` 服务入口和第一代服务装配层已经移除。V2 与旧架构隔离，仅保留可迁移的 Broker、行情、数据库和数据采集能力。

## 当前里程碑

已经实现：

- 独立 FastAPI V2 控制面、健康检查、OpenAPI 和有界 SSE 事件流。
- 多市场领域模型：A 股、美股、加密货币和外汇。
- `observe / paper / live` 运行模式基础以及信号、决策、订单状态模型。
- React + TypeScript 工作台：策略会话、K 线、信号覆盖层、聊天、Prompt 版本和决策时间线。
- cpptdx HTTP 行情适配器：A 股快照、分钟 K 线、健康检查和数据新鲜度。
- cpptdx 不可用时明确显示 `DEMO DATA`，Broker 和模型未配置时不会伪装为已连接。

尚未实现：

- Session 和 Prompt/Strategy 版本的数据库持久化。
- OpenAI、DeepSeek、Claude 的 V2 模型调用链。
- Paper Broker、QMT/东方财富 V2 Broker Adapter 和真实自动下单。
- QMT 实时行情主源及 cpptdx 主备切换。

因此当前版本用于架构和界面联调，不能用于真实自动交易。

## 目录

```text
trading_v2/       # 独立 FastAPI、领域模型、事件流、行情接口
web_v2/           # React + TypeScript Vibe Trading 工作台
docs/v2/          # V2 架构、数据模型、API 和交易生命周期
curs/broker/      # 保留的 QMT/东方财富 Broker 能力
curs/collection/  # 保留的数据采集能力
data_collection/  # 每日热点数据采集与导入
test/             # V2 与保留模块测试
```

## 安装

后端：

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
Copy-Item .env.v2.example .env
```

前端：

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm install
```

敏感配置必须放在 `config.local.yml`、环境变量或密钥服务中，不要提交 API Key、Broker 密码或会话文件。

## 启动

启动 V2 后端：

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m trading_v2
```

默认地址：

- API：`http://127.0.0.1:8010/api/v2`
- OpenAPI：`http://127.0.0.1:8010/docs`
- cpptdx：`http://127.0.0.1:8022`

启动 V2 前端：

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm run dev
```

打开 `http://127.0.0.1:5173`。Vite 会将 `/api` 代理到 8010 端口。

## cpptdx

通过 `.env` 配置：

```dotenv
TRADING_V2_CPPTDX_BASE_URL=http://127.0.0.1:8022
TRADING_V2_CPPTDX_TIMEOUT_SECONDS=3
```

当前支持：

- `GET /api/v2/market/status`
- `GET /api/v2/market/bars?instrument=cn_equity:XSHG:600000&timeframe=5m&limit=200`
- `POST /api/v2/market/snapshots`

cpptdx 仅作为 A 股分钟 K 线、快照和补齐数据源，不承担 Broker 交易。

## Broker 配置

保留的 QMT 与东方财富代码位于 `curs/broker/`。V2 Adapter 尚未接入，所以配置 Broker 不代表 V2 已获得下单能力。

示例配置：

```yaml
broker: qmt

qmt:
  path: ""
  account_id: ""
  trader_name: ""

eastmoney:
  account_no: ""
  password: ""
  session_file: "data/eastmoney_trader.session"
```

东方财富依赖网页交易接口，接口或登录校验变化可能导致失效。首次接入必须先使用只读连接测试，再使用模拟或审批模式验证。

## 测试

```powershell
# V2
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v

# 前端生产构建
cd web_v2
npm run build
```

## 设计文档

- [V2 架构](docs/v2/ARCHITECTURE.md)
- [V2 数据模型](docs/v2/DATA_MODEL.md)
- [V2 API](docs/v2/API.md)
- [V2 交易生命周期](docs/v2/TRADING_LIFECYCLE.md)
- [English Documentation](README_EN.md)
