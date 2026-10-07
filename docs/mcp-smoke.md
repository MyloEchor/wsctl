# MCP stdio 闭环验证

这个脚本启动真实的 `wsctl-mcp` 子进程，并通过 MCP 协议完成：

1. `initialize`
2. `tools/list`
3. 调用当前 Buildroot 工作区只读工具
4. 在临时预览工作区创建任务
5. 通过 `task_list` 和 `get_context` 读回

运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/mcp_smoke.py \
  --legacy-root /path/to/buildroot-workspace-framework \
  --project echolife-rk3576
```

脚本使用临时目录，不修改当前工作区，也不需要修改 Codex/Claude 的用户配置。

