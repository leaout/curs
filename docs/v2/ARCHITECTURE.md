# Vibe Trading V2 架构设计

## 1. 目标与边界

V2 是一套独立的实时交易系统。用户围绕一个长期对话 Session 创建和修改策略，系统在 K 线闭合后检测候选信号，只在出现候选信号时调用大模型，再由确定性风控和执行模块决定是否下单。

V2 明确弃用旧 Flask UI、旧 Engine、`StrategyManager`、动态 Python 策略加载和旧页面接口。旧代码仅允许作为以下能力的迁移来源：

- 东方财富账户与交易接入。
- cpptdx 行情、数据库和数据采集能力。
- 已验证的股票代码、市场和订单状态转换逻辑。

旧对象不得进入 V2 领域层。复用代码必须被 V2 Adapter 包装，并在边界转换成统一模型。

## 2. 设计原则

1. **对话即策略工作区**：一个 `TradingSession` 包含对话、Prompt、策略版本、运行状态和审计轨迹。
2. **模型不是交易权限主体**：模型只能生成结构化策略或 `Decision`，不能直接调用 Broker。
3. **少量稳定接口**：只有行情、模型和 Broker 使用可替换接口，不建设通用插件框架。
4. **信号驱动模型调用**：Tick、K 线和指标由本地代码处理；没有候选信号就不调用模型。
5. **确定性安全边界**：交易时段、仓位、价格、T+1、重复订单和损失限制全部由代码执行。
6. **版本不可覆盖**：聊天造成的 Prompt 或策略变化生成新版本，历史订单始终可追溯到当时版本。
7. **事件可审计**：信号、模型输入摘要、决策、风控、审批和订单状态以只追加事件记录。
8. **简单部署优先**：第一阶段采用单后端进程、React Web，以及开发 SQLite/生产 PostgreSQL；不引入 Kafka、Redis 或通用 Agent 框架。

## 3. 总体结构

```text
                           ┌──────────────────────────────┐
                           │ React Vibe Trading Workspace │
                           │ Chat | K-line | Timeline     │
                           └──────────────┬───────────────┘
                                          │ REST + SSE
┌──────────────┐  ticks/bars  ┌───────────▼──────────────┐
│ Market Feeds │─────────────►│ FastAPI Control Plane    │
│ Market       │              │ Session / Query / Stream │
└──────────────┘              └───────────┬──────────────┘
                                         │ commands
                             ┌───────────▼──────────────┐
                             │ Trading Runtime          │
                             │ Bar → Signal → Decision  │
                             │ → Risk → Execution       │
                             └───────┬───────────┬──────┘
                                     │           │
                          ┌──────────▼───┐   ┌───▼──────────────┐
                          │ Model Client │   │ Broker Adapter   │
                          │ OpenAI/...   │   │ Paper/Eastmoney  │
                          └──────────────┘   └──────────────────┘
                                     │
                             ┌───────▼────────┐
                             │ PostgreSQL     │
                             │ State + Events │
                             └────────────────┘
```

## 4. 固定模块

### 4.1 Control Plane

FastAPI 提供会话、策略版本、运行控制、行情查询、审批和订单 API。SSE 将对话输出、K 线、信号、决策和订单事件推送到 Web。双向操作继续使用普通 HTTP 命令，第一阶段不需要 WebSocket。

### 4.2 Session Service

维护长期 `TradingSession`：

- 保存用户和模型消息。
- 将自然语言修改编译为结构化策略草稿。
- 对比当前版本并生成可读变更摘要。
- 发布新 `PromptVersion` 和 `StrategyVersion`。
- 控制新版本在确定的 K 线边界生效。

Session 不直接消费 Tick，也不提交订单。

### 4.3 Market Pipeline

行情源统一输出 `Tick`、`Bar`、`MarketSnapshot` 和 `MarketStatus`。

- `CppTdxMarketDataProvider`：A 股分钟级 K 线、批量快照和历史补齐。通过 HTTP 访问独立 cpptdx 服务。
- 后续实时 Provider：按市场接入稳定数据源，统一输出标准 Tick、Bar 和健康状态。
- `MarketRouter`：根据配置选主源和备用源；切换前检查时间戳、交易日和数据连续性。
- `BarAggregator`：从标准 Tick 生成闭合分钟 K 线；只将闭合 Bar 送入信号引擎。

同一标的、周期、结束时间只能接受一根权威 Bar。来源切换必须写入事件，不能静默混合数据。

### 4.4 Strategy Runtime

结构化策略由白名单字段、指标、操作符和参数组成，不执行模型生成的 Python。`SignalEngine` 在闭合 Bar 上增量计算指标并产生 `CandidateSignal`。信号按 `session + strategy_version + instrument + timeframe + bar_end + signal_type` 幂等。

### 4.5 Agent Decision

`ContextBuilder` 只组装本次判断必要的内容：有效策略版本、最近 K 线与指标、账户摘要、持仓、市场状态和近期相关决策。模型返回严格 Schema 的 `Decision`。超时、限流、无效 JSON、版本不匹配或过期一律视为 `HOLD`。

### 4.6 Risk and Execution

`RiskEngine` 是最终硬门禁；`ExecutionEngine` 只接受已通过风控且仍在有效期内的 `OrderIntent`。支持：

- `observe`：记录完整决策链，不创建订单。
- `paper`：由 `PaperBroker` 模拟委托、成交、资金和持仓。
- `approval`：通过风控后等待人工批准，批准时重新校验行情与风险。
- `live`：通过真实 Broker 提交，必须开启账户级实盘权限。

### 4.7 Event Journal

业务表保存当前可查询状态，`audit_events` 保存不可变事实。写入关键状态与对应事件必须处于同一数据库事务。事件至少包含：

```text
event_id, event_type, occurred_at, session_id, correlation_id,
strategy_version_id, entity_type, entity_id, payload, schema_version
```

敏感凭证、完整 API Key 和 Broker 密码禁止进入事件载荷。

## 5. 允许替换的接口

```python
class MarketDataProvider:
    async def health(self): ...
    async def get_bars(self, instrument, timeframe, limit): ...
    async def stream_ticks(self, instruments): ...

class ModelProvider:
    async def complete_json(self, request, schema): ...

class Broker:
    async def account(self): ...
    async def positions(self): ...
    async def submit(self, order): ...
    async def cancel(self, broker_order_id): ...
    async def reconcile(self): ...
```

首批实现为 cpptdx；OpenAI、DeepSeek、Claude；Paper、东方财富。接口之外的业务模块使用普通 Python 服务和显式依赖注入。

## 6. 建议目录

```text
trading_v2/
├── api/             # FastAPI 路由、Schema、SSE
├── domain/          # 无外部依赖的领域类型和状态机
├── sessions/        # 对话、Prompt/策略版本及发布
├── market/          # 标准行情、路由、聚合、指标
├── signals/         # 指标、确定性规则、候选信号持久化与扫描
├── agent/           # 上下文和结构化模型决策
├── risk/            # 硬风控规则
├── execution/       # 委托、成交、对账
├── adapters/
│   ├── market/      # cpptdx、跨市场实时 Provider
│   ├── brokers/     # Paper、东方财富及后续市场适配器
│   └── models/      # OpenAI、DeepSeek、Claude
├── storage/         # SQLAlchemy、Repository、Alembic
└── main.py

web_v2/
└── src/
    ├── pages/       # Workspace、Orders、Settings
    ├── features/    # Chat、Chart、Timeline、Approval
    ├── api/
    └── stores/
```

## 7. 部署拓扑

第一阶段保持四个外部组件：

```text
React static assets
FastAPI + Trading Runtime (single process)
PostgreSQL
cpptdx service
```

东方财富登录会话按 Broker 需要独立维护。后台异步任务使用进程内 `asyncio` 有界队列；进程重启后从数据库恢复未完成 Run、待审批订单和待对账订单。只有实际负载证明单进程不足时才拆分 Runtime。

## 8. 架构约束

- `domain` 不得导入 FastAPI、SQLAlchemy、cpptdx 或旧 `curs` 模块。
- 旧 `curs` 代码只能由 `adapters` 导入。
- `agent` 不得导入任何 Broker 实现。
- Broker 只接受风控签发的执行命令，不接受模型原始输出。
- API 不直接访问适配器，通过应用服务发出命令。
- 所有外部输入在边界完成 Schema 校验、时间标准化和枚举转换。
- 架构测试应阻止 V2 导入 Flask、旧 Engine 和 `StrategyManager`。

## 9. 实施顺序

1. 建立领域模型、PostgreSQL 迁移、FastAPI 和 React Workspace 空壳。
2. 接入 cpptdx，完成 K 线查询、SSE 更新和数据新鲜度显示。
3. 建立 MarketRouter，并按市场接入实时行情 Provider 与主备切换。
4. 完成 Session 聊天、策略编译、版本预览和发布。
5. 完成候选信号、模型决策和图表标注。
6. 完成 Paper Broker、风控、订单状态机和事件时间线。
7. 增加 approval，最后小额度开放 live 与 Broker 对账。

## 10. 当前实现切片（2026-09）

已落地第 1、2、4 步以及第 5 步的“候选信号”部分：

- SQLAlchemy Repository 持久化 Session、Message、PromptVersion 和结构化策略 JSON。
- `StrategyCompiler` 只接受白名单指标与操作符，拒绝额外字段，不执行模型生成代码。
- DeepSeek、OpenAI、Anthropic 与 OpenAI-compatible HTTP Provider 通过同一接口接入。
- React 工作台以 API 数据为准；仅 K 线在 cpptdx 不可用时显示明确的演示数据。
- `SignalRuntime` 定时读取运行中 Session 的最新策略，只对闭合 Bar 计算白名单指标和规则。
- `candidate_signals_v2` 按 Session、策略版本、标的、周期、K 线时间和方向唯一去重。
- 信号经 SSE 推送，Web 将真实候选信号叠加到 K 线并显示在决策链中。
- 暂停会停止新信号；当前信号尚不会调用决策模型或产生订单。

下一切片是信号触发的模型决策、确定性风控与 Paper Broker。
