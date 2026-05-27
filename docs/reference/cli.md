# CLI 参考

入口名：`cve-monitor`（pip 安装后）或 `python -m src`（开发环境）。

## 全局帮助

```bash
$ cve-monitor --help

Usage: cve-monitor [OPTIONS] COMMAND [ARGS]...

  Extensible security intelligence framework.

Commands:
  version    Print version and exit.
  serve      Start the web dashboard + embedded scheduler.
  collect    Run one collection cycle synchronously and exit.
  list       List registered plugins.
  db         Database administration.
```

## `serve`

启动 Web 仪表盘 + 内嵌调度器。

```bash
cve-monitor serve [--host HOST] [--port PORT] [--reload]
```

| 参数 | 默认 | 来源 |
| --- | --- | --- |
| `--host` | `127.0.0.1` | `CVE_WEB_HOST` |
| `--port` | `8000` | `CVE_WEB_PORT` |
| `--reload` | 关 | 代码改动自动重启（仅开发） |

## `collect`

跑一轮采集 + 通知派发，结束即退出。适合 cron / 调试。

```bash
cve-monitor collect [--name COLLECTOR_NAME] [--once|--loop]
```

| 参数 | 说明 |
| --- | --- |
| `--name X` | 只跑名为 X 的 collector（其他全跳过） |
| `--once` | 一次性（当前唯一支持的模式；`--loop` 预留） |

## `list`

```bash
cve-monitor list collectors    # 列出所有已注册的采集器
cve-monitor list notifiers     # 列出所有已注册的通知渠道
```

输出每行：`name  enabled  description`。`enabled=no` 通常意味着环境变量没配齐。

## `db`

数据库管理。

```bash
cve-monitor db init             # 建所有表（已存在不影响）
cve-monitor db reset --yes      # ⚠️ DROP 所有表后重建。需 --yes 跳过确认
```

`reset` 是破坏性操作 — 不带 `--yes` 会交互确认。

## `version`

```bash
cve-monitor version
# cve-monitor 1.0.0
```

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 正常完成 |
| 1 | collector 执行出错（仅 `collect --name X` 时） |
| 2 | CLI 参数错误（Typer 内置） |
