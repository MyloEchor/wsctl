# 原型架构

```text
workspace registry
  -> .wsctl/workspace.yaml
  -> Markdown/YAML entities
  -> SQLite/FTS5 derived index
  -> services
  -> CLI and MCP adapters
```

核心原则：

- 管理面与执行面分离：wsctl 不执行构建、部署或烧写。
- CLI 与 MCP 共用 services，避免两套行为。
- Markdown/YAML 是事实源，SQLite 是可重建缓存。
- 默认只读；写入需要每个 workspace 显式 `allow_write`。
- 删除默认归档，purge 必须显式确认。
- 文件写入与 Git 提交分开。

