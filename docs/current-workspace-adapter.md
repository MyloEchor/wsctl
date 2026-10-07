# 当前 Buildroot 工作区适配器

适配器给现有工作区增加 MCP 调用面，但不移动原有事实：

- `west.yml`
- `management/`
- `platforms/`
- `products/`
- `knowledge/`

仍然由当前工作区维护。

## 架构

```text
MCP client
  -> wsctl-mcp
  -> legacy adapter
  -> current tools/wsctl source
  -> current workspace facts
```

适配器对原 CLI 调用做一层 JSON-safe 桥接，解决原 CLI 在 Python 3.14 下
YAML 日期对象不可 JSON 序列化的问题。它不修改原仓库。

## 权限

当前适配器只暴露：

- 只读状态；
- 上下文；
- 搜索/列表；
- 构建、测试、烧写计划。

不暴露：

- `build --execute`
- `test --execute`
- `deploy approve`
- `deploy apply`
- `release create --execute`
- `branches ensure --execute`
- `worktree ensure --execute`

以后如果要把执行权暴露给 MCP，应单独启用并使用原审批记录。

