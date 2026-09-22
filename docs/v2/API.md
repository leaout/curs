# Vibe Trading V2 API 设计

## 1. 约定

- 基础路径：`/api/v2`。
- JSON 字段使用 `snake_case`，时间使用 ISO 8601 UTC。
- 写操作支持 `Idempotency-Key`，创建订单、审批和发布版本时强制要求。
- 分页使用游标：`?cursor=...&limit=50`。
- 命令成功返回资源或 `202 Accepted + operation_id`；长过程通过 SSE 汇报。
- API Key、Broker 密码和令牌只接受写入，不通过任何读取接口回显。

统一错误：

```json
{
  "error": {
    "code": "STRATEGY_VALIDATION_FAILED",
    "message": "策略包含不支持的指标",
    "details": [{"path": "entry.all[0].field", "reason": "unknown_field"}],
    "request_id": "..."
  }
}
```

## 2. Session 与聊天

当前已实现 `POST/GET /sessions`、`GET /sessions/{id}`、`POST /messages`、`POST /pause` 和 `POST /resume`。表中其余接口为后续契约。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/sessions` | 创建策略对话 Session |
| `GET` | `/sessions` | Session 列表 |
| `GET` | `/sessions/{id}` | 工作区快照 |
| `PATCH` | `/sessions/{id}` | 修改名称等非交易字段 |
| `POST` | `/sessions/{id}/messages` | 发送消息并启动流式回复 |
| `GET` | `/sessions/{id}/messages` | 分页读取对话 |
| `POST` | `/sessions/{id}/pause` | 暂停信号处理 |
| `POST` | `/sessions/{id}/resume` | 恢复信号处理 |
| `POST` | `/sessions/{id}/archive` | 归档，不删除审计数据 |

发送自然语言修改：

```http
POST /api/v2/sessions/9d.../messages
Idempotency-Key: msg-20260921-001
```

```json
{
  "content": "把放量条件从 2 倍改成 1.5 倍，只在上午交易",
  "expected_strategy_version": 7
}
```

当前同步返回助手消息；模型调用超时或校验失败时，消息会说明原因且版本保持草稿：

```json
{
  "id": "...",
  "session_id": "...",
  "role": "assistant",
  "content": "已保存你的修改，但暂未生成可运行策略……",
  "version": 2,
  "status": "complete",
  "created_at": "2026-09-22T08:00:00Z"
}
```

后续异步化后再引入 `operation_id`；`expected_strategy_version` 与幂等键也尚未实现。

## 3. 策略版本

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/strategy` | 当前生效版本和最新草稿 |
| `GET` | `/sessions/{id}/strategy/versions` | 版本历史 |
| `GET` | `/strategy-versions/{version_id}` | 获取具体版本 |
| `GET` | `/strategy-versions/{version_id}/diff?against=...` | 结构化差异 |
| `POST` | `/strategy-versions/{version_id}/publish` | 发布草稿 |
| `POST` | `/sessions/{id}/rollback` | 基于历史版本创建并发布新版本 |
| `POST` | `/strategy-versions/{version_id}/validate` | 再次执行 Schema 与语义校验 |

发布请求：

```json
{
  "expected_active_version": 7,
  "effective_policy": "next_closed_bar",
  "reason": "用户确认聊天生成的修改"
}
```

`observe` 和 `paper` 可由用户配置聊天修改自动发布；`approval` 和 `live` 必须显式发布。发布不会修改已经创建的信号或正在运行的 Agent Run。

## 4. 运行控制

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/runtime` | 行情、模型、Broker 与运行状态 |
| `PUT` | `/sessions/{id}/mode` | 切换运行模式 |
| `POST` | `/sessions/{id}/start` | 启动 Session Runtime |
| `POST` | `/sessions/{id}/stop` | 有序停止，不撤销已提交订单 |
| `POST` | `/risk/kill-switch/engage` | 全局禁止新增订单 |
| `POST` | `/risk/kill-switch/release` | 解除，要求高权限及原因 |
| `GET` | `/risk/limits` | 当前全局风险限制 |

切换到 `live` 时后端必须检查：账户实盘权限、Broker 健康、行情新鲜度、风险配置、未完成对账和操作者权限。不能仅依赖前端确认框。

## 5. 行情与图表

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/market/instruments/search?q=...` | 搜索标准标的 |
| `GET` | `/market/bars` | 查询 K 线 |
| `GET` | `/market/status` | cpptdx/QMT 健康与延迟 |
| `GET` | `/sessions/{id}/annotations` | 查询信号、决策、风控和成交标注 |

K 线查询示例：

```http
GET /api/v2/market/bars?instrument=CN_EQUITY:XSHG:600000&timeframe=5m&from=...&to=...
```

当前返回的每根 Bar 包含 `source` 和 `is_closed`；后续数据路由层会增加 `quality`。图表默认只用闭合 Bar 计算指标，最后一根未闭合 Bar 仅用于视觉展示。

标注响应：

```json
{
  "items": [{
    "id": "...",
    "type": "model_buy",
    "market_time": "2026-09-21T02:30:00Z",
    "price": "12.35",
    "label": "AI 买入 82%",
    "event_id": "...",
    "correlation_id": "..."
  }]
}
```

## 6. 信号、决策与时间线

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/signals` | 候选信号列表 |
| `GET` | `/signals/{id}` | 信号及触发事实 |
| `GET` | `/signals/{id}/decision` | 模型决策与校验结果 |
| `GET` | `/sessions/{id}/timeline` | 聚合后的审计时间线 |
| `GET` | `/events/{event_id}` | 单个审计事件详情 |

面向 UI 的接口返回必要摘要；模型原始响应仅在诊断权限下可见，并在返回前脱敏。

## 7. 审批、订单与持仓

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/approvals?status=pending` | 待审批委托 |
| `POST` | `/approvals/{id}/approve` | 批准，随后重新执行时效与风控校验 |
| `POST` | `/approvals/{id}/reject` | 拒绝并记录原因 |
| `GET` | `/orders` | 订单列表 |
| `GET` | `/orders/{id}` | 订单及 Broker 事件 |
| `POST` | `/orders/{id}/cancel` | 请求撤单 |
| `GET` | `/accounts/{id}` | 脱敏账户摘要 |
| `GET` | `/accounts/{id}/positions` | 当前持仓 |

批准请求不直接表示一定下单。系统必须重新检查决策有效期、最新行情、可用资金、持仓和 Kill Switch；失败时返回新的风险拒绝事件。

## 8. 连接与配置

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/connections` | 行情、模型、Broker 配置状态 |
| `POST` | `/connections/{id}/test` | 执行无交易连接测试 |
| `PUT` | `/model-profiles/{id}` | 更新模型配置；密钥为 write-only |
| `GET` | `/model-profiles` | 返回模型名、超时及 `secret_configured` |
| `PUT` | `/market-routing` | 配置 cpptdx/QMT 主备顺序 |

生产环境优先从环境变量或密钥服务读取凭证。API 不保存或返回明文密钥。

## 9. SSE 实时事件

```http
GET /api/v2/sessions/{id}/events?after=01J...
Accept: text/event-stream
```

事件信封：

```text
id: 01J...
event: decision.created
data: {"schema_version":1,"session_id":"...","correlation_id":"...","occurred_at":"...","payload":{...}}
```

首批 UI 事件：

```text
chat.delta / chat.completed
strategy.drafted / strategy.published
market.bar.closed / market.source.changed
signal.created
decision.created / decision.failed
risk.approved / risk.rejected
approval.requested / approval.resolved
order.updated
system.health.changed
```

客户端断线重连时发送最后收到的事件 ID。服务端先从审计事件补发，再继续实时推送；慢客户端超出缓冲区时断开并要求从游标恢复。

## 10. 健康检查与安全

- `GET /api/v2/health/live`：进程存活。
- `GET /api/v2/health/ready`：V2 Runtime 已启动；接入数据库后还要检查迁移状态。
- `GET /api/v2/status`：当前 Runtime 与组件状态。
- `GET /api/v2/market/status`：当前行情 Provider 健康和延迟。

所有改变交易行为的端点要求认证、角色权限和审计。浏览器使用同源安全 Cookie 与 CSRF 防护；若使用 Bearer Token，则不得保存到 Local Storage。API 日志禁止记录请求中的密钥和完整账户凭证。
