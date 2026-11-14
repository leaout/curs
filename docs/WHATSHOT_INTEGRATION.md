# WhatsHot 同花顺热股榜接入

## 当前采集方式

Curs 使用本机 Chrome 渲染 WhatsHot 上公开展示的同花顺 A 股热股榜，不需要 API Key、登录 Cookie，也不直接请求同花顺上游页面：

`https://whatshot.top/news/ths-10jqka?type=hot-stock&view=detail`

采集器读取页面中的股票、排名、热度、涨跌幅、概念摘要和页面更新时间，并将证券代码规范为 `NNNNNN.SH`、`.SZ` 或 `.BJ`。当前设置最多采集 100 条。榜单页面或访问校验方式变化时，解析可能失败。

## 自动同步时间

`run.py` 初始化 Web 服务时会启动单实例后台同步器，`--web-only` 同样支持。工作日北京时间 15:35 后检查当日数据；失败时每 15 分钟重试，最晚至 22:00。主机休眠、服务停止或数据库不可用期间不会完成同步。

同步成功需要有效榜单写入股票池和每日快照。失败不会把旧缓存标成当天数据。成功数据在股票池显示来源和本机采集时间；每日快照保存榜单来源。网页不提供可靠的最新成交价，因此榜单的价格字段不应用作实时行情。

旧 GitHub Actions 定时抓取、提交归档文件以及启动时导入归档的流程已删除。历史 JSON/CSV 归档不再参与服务同步。

## 环境配置

- 在运行 Curs 的主机安装 Google Chrome。
- 确保运行 Curs 的 Windows 用户（包括计划任务使用的账户）有权限启动 Chrome。
- 若无法自动发现 Chrome，在 `config.local.yml` 设置完整路径：

```yaml
whatshot:
  chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

也可设置环境变量 `WHATSHOT_CHROME_PATH`。页面地址、采集数量、渲染等待时间和超时在 `config.yml` 的 `whatshot` 节点配置。

## 手动同步与排错

1. 在 Web 管理页的“股票池”中点击“同步热点榜”。
2. 或调用 `POST /api/hotstocks/sync`。
3. 查看 `logs/` 中的服务日志、页面上的来源与采集时间，以及数据库当日快照。
4. 若没有新数据，确认服务在工作日 15:35–22:00 运行、Chrome 可由服务账户启动、数据库可用；随后检查日志中的 WhatsHot 页面渲染或解析错误。

命令行也可手动抓取并同步：

```powershell
python -m curs.collection.hot_stocks
```

不要从 GitHub Actions 归档文件恢复或覆盖当天数据。若 WhatsHot 不可用，页面会保留已有记录并由服务重试；它不会把旧榜单伪装成新榜单。
