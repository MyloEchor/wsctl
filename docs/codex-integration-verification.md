# Codex 宿主 MCP 验证

日期：2026-10-08

## 验证目标

确认外部 `wsctl-mcp` 不只可以通过 SDK 调用，还能被 Codex 识别并在真实宿主中调用。

## 配置识别

使用临时 `CODEX_HOME` 注册 stdio MCP server：

```bash
CODEX_HOME="$tmp" codex mcp add wsctl -- \
  /home/cj/Tech/wsctl/.venv/bin/wsctl-mcp \
  --legacy-workspace /home/cj/buildroot-workspace-framework

CODEX_HOME="$tmp" codex mcp list
```

结果：`wsctl` server 显示为 `enabled`，command/args 正确。

## 实际工具调用

使用临时配置覆盖，不写真实 `~/.codex/config.toml`：

```bash
codex \
  -c 'mcp_servers.wsctl.command="/home/cj/Tech/wsctl/.venv/bin/wsctl-mcp"' \
  -c 'mcp_servers.wsctl.args=["--legacy-workspace","/home/cj/buildroot-workspace-framework"]' \
  -c 'mcp_servers.wsctl.default_tools_approval_mode="approve"' \
  exec --ephemeral --skip-git-repo-check --sandbox read-only \
  -C /home/cj/Tech/wsctl --json \
  '只使用 wsctl MCP 的 legacy_project_list 工具，回复项目数量。不要运行 shell。'
```

结果：

- Codex 发起了 `mcp_tool_call`；
- server 为 `wsctl`；
- tool 为 `legacy_project_list`；
- 调用状态为 `completed`；
- 最终回答为 `3 个项目`。

## 审批模式

Codex 的 MCP 配置支持：

```toml
[mcp_servers.wsctl]
default_tools_approval_mode = "approve"
```

取值：

- `auto`
- `prompt`
- `writes`
- `approve`

当前 legacy adapter 只暴露只读/计划工具，所以 `approve` 适用于当前专用 server。
如果同一个 server 以后同时暴露写入或执行工具，应按工具单独设置审批模式。

