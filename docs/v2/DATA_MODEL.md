# Vibe Trading V2 数据模型

## 1. 通用约定

- 主键使用不可预测的 UUID；所有关联显式保存 ID。
- 数据库存储 UTC 时间，API 使用 ISO 8601；市场时间同时保留交易所时区。
- 金额、价格和数量使用定点数，不使用二进制浮点数。
- 可变配置采用版本表；历史版本不可更新或删除。
- 每条交易链共享 `correlation_id`，通常从候选信号创建时生成。
- 外部事件使用唯一 `source_event_id` 或幂等键，重复输入不得产生重复订单。

## 2. 会话与版本

当前数据库先以三个 V2 表实现最小闭环：`trading_sessions_v2`、`trading_messages_v2`、`trading_prompt_versions_v2`。其中 PromptVersion 同时保存自然语言输入、编译后的策略 JSON、模型身份和警告；正式发布/回滚加入后再拆分独立 `strategy_versions`。

### 2.1 `trading_sessions`

一个策略工作区对应一个长期 Session。

| 字段 | 含义 |
| --- | --- |
| `id` | Session ID |
| `name` | 用户可编辑名称 |
| `status` | `draft/active/paused/archived` |
| `mode` | `observe/paper/approval/live` |
| `active_strategy_version_id` | 当前生效策略版本 |
| `active_prompt_version_id` | 当前决策 Prompt 版本 |
| `account_id` | 绑定的账户，observe 可为空 |
| `created_at/updated_at` | 创建与最后变更时间 |

### 2.2 `session_messages`

| 字段 | 含义 |
| --- | --- |
| `id`, `session_id` | 消息及所属 Session |
| `role` | `user/assistant/system/tool` |
| `content` | 展示文本 |
| `kind` | `chat/change_request/change_summary/approval/system_notice` |
| `status` | `pending/streaming/completed/failed` |
| `model_run_id` | 产生该消息的模型运行，可为空 |
| `created_at` | 写入时间 |

消息只追加。编辑通过新消息完成，不覆盖历史。

### 2.3 `prompt_versions`

保存用于候选信号决策的系统指令、输出 Schema 版本、模型参数及内容哈希。`version` 在 Session 内单调递增。

### 2.4 `strategy_versions`

| 字段 | 含义 |
| --- | --- |
| `id`, `session_id`, `version` | 版本身份 |
| `status` | `draft/published/superseded/rejected` |
| `spec` | 通过 Schema 校验的结构化策略 JSON |
| `prompt_version_id` | 与该策略配套的 Prompt |
| `based_on_version_id` | 修改来源 |
| `change_summary` | 面向用户的差异摘要 |
| `created_by_message_id` | 触发变更的聊天消息 |
| `published_at` | 发布时间 |
| `effective_from` | 生效边界时间 |

聊天要求修改策略时先创建 `draft`。发布操作原子地确定 `effective_from` 并更新 Session 当前版本。已经开始的 `AgentRun` 继续使用创建时锁定的版本。

结构化 `spec` 至少包含：

```json
{
  "universe": {"instruments": ["CN_EQUITY:XSHG:600000"]},
  "timeframe": "5m",
  "indicators": [{"name": "ema", "params": {"period": 20}}],
  "entry": {"all": []},
  "exit": {"any": []},
  "decision": {"enabled": true, "minimum_confidence": "0.75"},
  "position": {"allocation_pct": "0.05"},
  "risk_overrides": {}
}
```

## 3. 行情模型

### 3.1 `InstrumentId`

由 `asset_class`、`venue`、`symbol` 组成，例如 `CN_EQUITY:XSHG:600000`。显示代码不是主键，适配器负责外部代码映射。

### 3.2 `Tick` 与 `Bar`

`Tick` 包含成交/快照时间、接收时间、价格、数量、买卖盘摘要和来源。`Bar` 包含周期、开高低收、成交量、成交额、开始/结束时间、是否闭合、来源和质量状态。

可选持久化表：

- `market_bars`：仅保存实际用于决策或图表缓存的标准 Bar。
- `market_source_events`：记录断线、恢复、主备切换和缺口修复。

所有行情对象包含：

```text
source, market_time, received_at, trading_day,
quality = fresh | stale | gap | corrected
```

模型和信号引擎只处理 `closed=true` 且质量允许的 Bar。

## 4. 信号、决策与运行

### 4.1 `candidate_signals`

| 字段 | 含义 |
| --- | --- |
| `id`, `correlation_id` | 信号及整条交易链标识 |
| `session_id`, `strategy_version_id` | 锁定策略版本 |
| `instrument`, `timeframe`, `bar_end` | 图表定位信息 |
| `signal_type` | `entry/exit/reduce/alert` |
| `facts` | 触发条件和指标快照 |
| `status` | `created/deduplicated/evaluating/decided/expired` |
| `expires_at` | 最迟决策时间 |

唯一键：`session_id + strategy_version_id + instrument + timeframe + bar_end + signal_type`。

### 4.2 `agent_runs`

每个候选信号创建一次 Agent Run。保存上下文摘要哈希、模型配置版本、开始/结束时间、状态、耗时和错误类型。原始敏感账户数据不进入 Prompt 或日志。

状态：

```text
QUEUED → CONTEXT_READY → MODEL_RUNNING → DECIDED
                  └───────────────→ FAILED/TIMED_OUT
```

### 4.3 `model_decisions`

模型返回并经 Schema 校验后的不可变记录：

```json
{
  "action": "BUY",
  "confidence": "0.82",
  "order_type": "LIMIT",
  "limit_price": "12.35",
  "stop_loss": "11.80",
  "take_profit": "13.60",
  "valid_until": "2026-09-21T02:31:00Z",
  "reason": "5 分钟突破且量能满足策略条件"
}
```

数据库同时保存 `signal_id`、`agent_run_id`、`prompt_version_id`、模型提供商、模型名、响应哈希和校验结果。无效或超时响应也要保存失败原因，但不得形成订单意图。

## 5. 风控与执行

### 5.1 `risk_decisions`

保存 `approved/rejected`、逐条规则结果、账户快照 ID、行情时间、策略风险版本和最终允许的数量/价格。模型建议数量不直接成为订单数量，由 Allocation 与 Risk 计算。

### 5.2 `orders`

| 字段 | 含义 |
| --- | --- |
| `id`, `client_order_id` | 本地与幂等订单 ID |
| `session_id`, `signal_id`, `decision_id`, `risk_decision_id` | 完整来源链 |
| `mode` | 创建时运行模式 |
| `broker_account_id` | Broker 账户 |
| `instrument`, `side`, `type`, `quantity`, `price` | 标准委托字段 |
| `status` | 本地订单状态 |
| `broker_order_id` | 外部订单 ID，可为空 |
| `submitted_at/updated_at` | 生命周期时间 |

### 5.3 `order_events`

只追加保存提交、确认、部分成交、成交、撤单、拒绝和对账修正。`orders.status` 是事件归并后的当前投影。

订单状态：

```text
CREATED → RISK_APPROVED → PENDING_APPROVAL → SUBMITTING
       → SUBMITTED → PARTIALLY_FILLED → FILLED

终态/异常：RISK_REJECTED, APPROVAL_REJECTED, EXPIRED,
SUBMIT_FAILED, REJECTED, CANCELLED, UNKNOWN
```

### 5.4 快照

- `account_snapshots`：净值、现金、可用资金、当日盈亏、来源时间。
- `position_snapshots`：账户、标的、总数量、可用数量、成本和市值。

风控决策引用实际使用的快照 ID，确保日后可以还原判断依据。

## 6. 图表标注

图表标注不需要独立事实表，可由领域事件投影生成 `chart_annotations` 读模型：

| 类型 | 图表表现 | 来源 |
| --- | --- | --- |
| `candidate_signal` | 空心箭头 | CandidateSignal |
| `model_buy/sell/hold` | AI 标签 | ModelDecision |
| `risk_rejected` | 红色盾牌 | RiskDecision |
| `approval_pending` | 时钟 | Approval |
| `order_submitted` | 委托线 | OrderEvent |
| `fill` | 实心成交点 | OrderEvent |
| `strategy_changed` | 垂直版本线 | StrategyVersion |

每个标注含 `instrument`、`timeframe`、`market_time`、`price`、`event_id` 和可展开的摘要。点击标注可用 `correlation_id` 定位右侧对话及底部时间线。

## 7. 审计事件

`audit_events` 是只追加账本：

```text
SESSION_CREATED
MESSAGE_ADDED
STRATEGY_DRAFTED / STRATEGY_PUBLISHED
MARKET_SOURCE_SWITCHED
SIGNAL_CREATED
MODEL_REQUESTED / MODEL_DECIDED / MODEL_FAILED
RISK_APPROVED / RISK_REJECTED
APPROVAL_REQUESTED / APPROVAL_RESOLVED
ORDER_SUBMITTED / ORDER_UPDATED / ORDER_RECONCILED
MODE_CHANGED / KILL_SWITCH_CHANGED
```

事件载荷采用版本化 JSON Schema。任何会影响实盘行为的用户动作必须记录操作者、来源 IP/客户端、前后状态和原因。

## 8. 关联关系

```text
TradingSession
 ├─ SessionMessage*
 ├─ PromptVersion*
 ├─ StrategyVersion*
 │    └─ CandidateSignal*
 │         └─ AgentRun ─ ModelDecision
 │                         └─ RiskDecision
 │                              └─ Order ─ OrderEvent*
 └─ AuditEvent*
```

历史查询以版本和事件为准；当前 UI 状态可以由投影表和缓存加速，但投影不得成为唯一审计来源。
