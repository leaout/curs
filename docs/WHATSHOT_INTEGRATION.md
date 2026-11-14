# WhatsHot 同花顺热股榜采集

## 数据来源和方式

Curs 从 WhatsHot 的公开网页抓取同花顺 A 股热股榜，不调用开发者 API，不需要 API Key，也不向同花顺网站直接发请求。榜单页面为：

`https://whatshot.top/news/ths-10jqka?type=hot-stock&view=detail`

页面由 Chrome 无头模式渲染，采集器解析页面中的股票行、排名、热度、涨跌幅、概念摘要和榜单更新时间。当前页面通常显示实时热榜 Top 100。页面结构和访问策略可能变化；若 WhatsHot 返回校验页或页面没有股票行，采集会失败，不会把旧缓存当成当天榜单。

## 环境要求

- Windows 本机服务：安装 Google Chrome，并确保运行 Curs 的账户可以执行它。若服务以 SYSTEM 运行而 Chrome 只安装在个人目录，请在 `config.local.yml` 中配置机器可访问的完整 `chrome_path`。
- Python 依赖：安装项目 `requirements.txt`，其中包含 Windows 时区支持所需的 `tzdata`。
- 可选的手动 GitHub Actions 归档：工作流使用 `browser-actions/setup-chrome` 安装 Chrome。每日自动抓取已停用。
- 不需要 `WHATSHOT_API_KEY`、`WHATSHOT_API_BASE_URL` 或站点登录 Cookie。

如果 Chrome 未安装到常见路径，可在 `config.local.yml` 设置：

```yaml
whatshot:
  chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

也可以使用环境变量 `WHATSHOT_CHROME_PATH`。榜单地址、抓取数量、浏览器渲染等待时间和超时可在 `config.yml` 的 `whatshot` 节点调整。

## 数据链路

1. Chrome 打开公开热股榜页面并等待页面渲染。
2. 采集器解析并标准化股票代码为 `NNNNNN.SH`、`.SZ` 或 `.BJ`，最多取 100 只。
3. `curs.collection.hot_stocks.get_hot_stocks()` 保存短期缓存；Curs Web 服务工作日北京时间 15:35 后直接抓取并同步，失败时每 15 分钟重试到 22:00，不会把旧缓存当作当天数据。也可以在“管理 → 股票池”点击“同步热点榜”，或调用 `POST /api/hotstocks/sync`。股票池和日快照均写入成功后才将当天标记为完成。
4. 原有 GitHub Actions 每日抓取已关闭；需要额外 JSON/CSV 归档时，可在 GitHub Actions 页面手动运行“手动归档热股榜”。归档文件不会随 Curs 启动自动导入，也不会覆盖服务同步结果。

网页没有可靠提供最新成交价，因此价格填 `0`；涨跌幅来自榜单行说明。股票池列表会标出 `WhatsHot/同花顺网页` 来源及本机采集时间；更新时间取页面显示的“刚刚更新”或“X 分钟前更新”，按采集时刻估算。此前同步的记录没有来源字段时会显示“来源未记录”，不会猜测其数据来源。

## 手动采集

```powershell
python -m curs.collection.hot_stocks
```

或在“管理 → 股票池”点击“同步热点榜”。检查 `logs/` 中的采集日志和 `data/collected/` 中的 JSON/CSV。
