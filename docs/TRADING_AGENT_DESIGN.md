# Trading Agent 设计文档

## 1. 目标

构建一个面向 A 股、加密货币、美股和外汇的实时 Trading Agent。用户通过自然语言定义策略，本地指标先发现候选信号，模型只对候选信号做结构化判断，最终由确定性风控决定是否允许下单。

系统不提供传统历史回测。验证能力以观察模式、模拟交易、实盘事件回放和版本对比为主。

## 2. 设计原则

1. 不沿用旧项目的核心架构，只复用已经工作的行情和 Broker 接入。
2. 不建设通用插件内核。只有行情、模型和 Broker 使用稳定接口。
3. 模型不能直接访问 Broker，不能绕过硬风控。
4. 所有外部数据在边界转换成统一类型。
5. 每个信号、决策、风控结果和订单结果都必须可追踪。
6. 默认安全：未配置、超时、异常和非法输出均不产生真实订单。

## 3. 总体架构

```text
Market Data → Bar/Indicator → Signal Detector → Model Decision
                                                   ↓
Web/Config ← Journal/Status ← Broker Execution ← Risk Gate
```

固定模块包括领域模型、指标、信号、Agent Runtime、风控、执行、日志和 Web 控制面。可替换边界只有：

- `MarketDataProvider`：QMT、交易所 WebSocket 或第三方行情。
- `ModelProvider`：OpenAI、DeepSeek、Claude、兼容接口。
- `BrokerAdapter`：QMT、东方财富及未来的 Binance、IBKR。

## 4. 实时决策流程

1. 行情适配器产生标准 Tick 或闭合 Bar。
2. 本地增量计算指标，确定性条件发现候选信号。
3. 去重器按策略、标的、周期和信号类型消除重复请求。
4. Context Builder 仅提供本次决策所需的指标、账户摘要和市场状态。
5. 模型返回有严格 Schema 的 `Decision`。
6. Runtime 校验 signal ID、置信度、有效期和字段范围。
7. Allocator 生成 `OrderIntent`，Risk Gate 执行硬限制。
8. 根据运行模式阻断、模拟或提交订单。
9. 全过程写入只追加审计日志。

## 5. 运行模式

| 模式 | 模型决策 | 风控 | Broker |
| --- | --- | --- | --- |
| `observe` | 是 | 是 | 永不调用 |
| `paper` | 是 | 是 | 仅模拟成交 |
| `live` | 是 | 是 | 调用真实账户 |

系统默认 `observe`。切换到 `live` 还要求账户自身的 `live_trading` 开关为真。

## 6. 模型使用边界

模型用于：

- 自然语言生成并修订结构化策略定义。
- 候选信号产生后进行一次有时限的决策。
- 离线解释事件和提出策略改进建议。

模型不用于：

- 持续接收所有 Tick。
- 计算基础技术指标。
- 判断账户是否允许交易。
- 直接构造或提交券商 API 请求。
- 自动修改正在运行的实盘策略。

## 7. 状态与可观测性

第一阶段使用 JSONL 记录事件。后续迁移到 PostgreSQL 时仍保留 append-only 语义。每条事件至少包含 `agent_id`、`strategy_id`、`signal_id`、时间、类型、输入版本和结果。

Web 页面通过只读状态 API 展示运行状态。后续增加事件流时使用 SSE；只有需要双向人工审批时才引入 WebSocket。

## 8. 当前接入

- QMT Tick 已转换为统一 Tick，并聚合为 1/5/15 分钟 Bar。
- QMT 和东方财富账户可通过旧账户接口适配为统一 Broker。
- OpenAI、DeepSeek、Claude 已统一为结构化决策接口。
- `run.py` 直接通过现有 Broker 工厂创建 Agent 专用账户，不依赖旧策略实例。
- `/trading-agent` 展示脱敏运行状态和配置说明。

当前实时行情桥只支持 QMT。其他市场必须先实现对应行情适配器，不能假装复用 QMT 数据。

## 9. 后续顺序

1. 实现一句话策略 API 和结构化预览页面。
2. 将策略注册从 YAML 迁移到 PostgreSQL。
3. 增加 SSE 决策时间线和订单状态追踪。
4. 增加独立 Paper Account，而不是依赖实盘账户快照。
5. 实现加密货币行情与 Broker，再扩展美股和外汇。
6. 用真实事件 Replay 比较模型、Prompt 和策略版本。
