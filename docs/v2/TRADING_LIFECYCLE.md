# Vibe Trading V2 交易生命周期

## 1. Session 是运行单位

每个交易策略对应一个长期 `TradingSession`。Session 同时承载：

- 用户与模型的持续对话。
- 当前 Prompt 和结构化策略版本。
- 绑定标的、周期、账户和运行模式。
- 信号、决策、风控、订单及成交时间线。
- K 线上的事件标注。

Session 可以暂停和恢复。归档只停止运行，不删除历史。

## 2. 从对话到生效策略

```text
用户消息
  ↓
模型识别意图：解释 / 查询 / 策略修改
  ↓（策略修改）
生成结构化 Strategy Draft + Prompt Draft
  ↓
Schema、指标白名单、市场规则和风险边界校验
  ↓
UI 展示自然语言摘要 + 字段 Diff
  ↓
发布新版本
  ↓
从下一根闭合 K 线开始生效
```

关键规则：

1. 聊天记录本身不可编辑；修正通过新消息完成。
2. 一次有效修改生成新的 `StrategyVersion`，必要时同时生成 `PromptVersion`。
3. 对话中仅做解释或查询时不生成版本。
4. `observe/paper` 可配置自动发布；`approval/live` 必须显式确认发布。
5. 版本在 `next_closed_bar` 边界原子切换，避免一根 K 线被两套条件处理。
6. 已产生的信号、模型调用、审批和订单继续引用原版本，禁止中途换 Prompt。
7. 回滚不是覆盖历史，而是基于旧内容创建一个新版本。

## 3. 实时行情生命周期

```text
cpptdx / QMT 原始数据
  ↓ Adapter 标准化
时间戳、交易日、代码和数值校验
  ↓
主备源选择与数据质量检查
  ↓
Tick / Snapshot → BarAggregator
  ↓
bar.updated（仅 UI）
  ↓
bar.closed（进入指标和信号引擎）
```

- cpptdx 主要用于分钟 K 线、快照、历史补齐和备用行情。
- QMT 主要用于实时 Tick 推送及 Broker 相关行情。
- 未闭合 K 线可以显示，但不能触发正式策略。
- 数据过期、缺口、交易日错误或来源冲突时标记质量问题并暂停对应标的决策。
- 主备切换产生 `MARKET_SOURCE_SWITCHED` 事件；切换后不得重复消费相同闭合 Bar。

## 4. 候选信号到模型决策

```text
闭合 Bar
  ↓
增量指标计算
  ↓
确定性策略条件
  ↓（满足）
CandidateSignal + correlation_id
  ↓ 幂等/冷却/过期检查
ContextBuilder
  ↓
一次结构化模型请求
  ↓
Decision 校验
```

只有候选信号会触发模型。Context 包含锁定版本、触发事实、必要 K 线与指标、账户/持仓摘要、市场状态及少量近期相关决策，不包含 Broker 凭证。

合法 Decision 必须满足：

- `signal_id` 和版本与请求一致。
- `action`、价格、置信度和理由满足 Schema。
- 决策仍在 `valid_until` 之前。
- 返回内容没有请求未授权的标的或账户。

模型超时、限流、网络错误、无效 JSON 或字段越界统一生成失败事件并安全降级为 `HOLD`。不得因模型失败直接使用上一次交易决策。

## 5. 风控生命周期

对 `BUY/SELL/REDUCE/EXIT` 决策生成 `OrderIntent`，随后按固定顺序检查：

1. Session 是否 active，模式是否允许。
2. Kill Switch、账户和 Broker 状态。
3. 信号与决策是否仍有效。
4. 行情是否新鲜、是否在交易时段。
5. 标的状态、涨跌停、最小价位和交易单位。
6. A 股 T+1、可用持仓和可用资金。
7. 单笔、单标的、总仓位和持仓数量限制。
8. 当日亏损、交易频率、冷却和重复订单限制。
9. 根据约束重新计算最终数量和价格。

任一规则拒绝即终止执行，记录全部规则结果并在 K 线上增加风险拒绝标注。模型不能覆盖风控结果。

## 6. 四种运行模式

| 模式 | 行情/信号 | 模型 | 风控 | 最终动作 |
| --- | --- | --- | --- | --- |
| `observe` | 真实 | 真实 | 真实校验 | 记录“若交易”结果，不创建订单 |
| `paper` | 真实 | 真实 | 真实规则 | Paper Broker 模拟委托和成交 |
| `approval` | 真实 | 真实 | 真实规则 | 等待人工批准后重新校验并提交真实 Broker |
| `live` | 真实 | 真实 | 真实规则 | 直接提交真实 Broker |

系统初始默认 `observe`。模式升级属于高风险操作：必须记录操作者和原因。`live` 还要求账户级 `live_trading_enabled`，进程配置和数据库状态必须同时允许。

## 7. 审批与执行

### 7.1 Approval

通过风控后创建限时审批项。用户批准时不复用旧风控结论，而是重新读取行情、资金、持仓和 Kill Switch。过期、版本变化或风险不再满足时不下单，并产生明确事件。

### 7.2 Order State Machine

```text
CREATED
  ├─→ RISK_REJECTED
  └─→ RISK_APPROVED
        ├─→ PENDING_APPROVAL → APPROVAL_REJECTED / EXPIRED
        └─→ SUBMITTING → SUBMITTED
                              ├─→ PARTIALLY_FILLED → FILLED
                              ├─→ CANCELLED
                              ├─→ REJECTED
                              └─→ UNKNOWN → RECONCILED
```

提交前创建唯一 `client_order_id`。超时后不能盲目重试提交；必须先向 Broker 查询是否已经受理。订单回报和定时对账共同推进状态。

## 8. K 线、聊天和时间线联动

同一业务事件通过 `correlation_id` 连接三个视图：

```text
K 线标注                    对话                    审计时间线
信号箭头 ───────────────► “为何触发？” ─────────► 条件与指标快照
AI BUY 标签 ─────────────► 模型理由 ─────────────► Prompt/模型版本
风险盾牌 ────────────────► 拒绝解释 ─────────────► 逐条风险结果
成交点 ──────────────────► 订单摘要 ─────────────► Broker 回报/对账
版本垂线 ────────────────► 修改消息与 Diff ───────► 发布者/生效边界
```

用户点击任一 K 线标注，UI 应定位对应聊天上下文和时间线。聊天中询问某次交易时，后端按事件 ID 构造解释上下文，而不是让模型凭记忆猜测。

## 9. 暂停、停止与 Kill Switch

- `pause session`：停止创建新信号；已经提交的订单继续接收回报。
- `stop runtime`：有序停止行情消费和新任务，不自动撤单。
- `kill switch`：全局禁止新订单和批准操作；是否撤销活动订单由独立显式命令决定。
- Broker 或行情异常：自动阻止新订单，但仍进行订单回报消费和对账。

这些动作不能隐含撤单或平仓，以免把恢复动作变成新的风险。需要撤单或平仓时必须显示目标范围并单独确认。

## 10. 崩溃恢复与对账

启动时按以下顺序恢复：

1. 读取 Kill Switch 和 Session 状态，不自动提升运行模式。
2. 连接数据库、行情源和 Broker，验证交易日与时钟。
3. 恢复未完成模型 Run；超过有效期的直接失败，不补做旧决策。
4. 恢复待审批项；过期项转为 `EXPIRED`。
5. 查询 Broker 活动订单与成交，按 `client_order_id/broker_order_id` 对账。
6. 对未知订单标记 `UNKNOWN` 并阻止相关账户新增订单，等待对账完成。
7. 从最后处理的闭合 Bar 游标恢复行情，幂等跳过已处理 Bar。

恢复过程中的每一步写入审计事件，并实时显示在系统时间线。

## 11. 图表事件顺序

同一根 Bar 上的标注按业务阶段排序：

```text
strategy_changed
→ candidate_signal
→ model_buy/model_sell/model_hold
→ risk_approved/risk_rejected
→ approval_pending/approval_resolved
→ order_submitted
→ partial_fill/fill/cancel/reject
```

图表价格坐标优先使用事件实际价格；没有价格的系统事件吸附在 Bar 收盘价。所有标注都显示事件来源时间，避免把页面接收时间误认为市场发生时间。

## 12. 策略演进

系统不提供传统回测。策略改进使用生产事件 Replay：

- 从历史 CandidateSignal、上下文摘要和行情快照重放新 Prompt/模型版本。
- 对比旧决策与新决策，但绝不向 Broker 发送重放订单。
- 自动进化只能生成候选草稿和评估报告，不能自动发布到 `approval/live`。
- 发布新版本后从新 Bar 开始观察，旧版本结果保留用于比较。

这使策略可以持续通过对话演进，同时保持每次改变可解释、可回滚、可审计。
