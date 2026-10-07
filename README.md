# wsctl

一个用于 AI 开发工作区的通用管理原型：

- 用 `.wsctl/` 保存 Git 友好的 Markdown/YAML 管理数据；
- 用 Python 包和 CLI 提供统一服务；
- 用 MCP 让支持 MCP 的 AI 开发工具发现和调用；
- 用 SQLite/FTS5 做本地检索索引，索引可随时重建；
- 不内置构建、测试、部署或烧写逻辑。

当前版本是外部实验原型，用来验证通用管理面能否适配现有工作流。

## 快速开始

```bash
python3 -m pip install -e '.[mcp]'

wsctl init /tmp/my-project
wsctl --root /tmp/my-project workspace add /tmp/my-project --allow-write
wsctl --root /tmp/my-project projects create demo --name "Demo Project"
wsctl --root /tmp/my-project create task \
  --title "写下第一条通用任务" \
  --project demo \
  --tag preview
wsctl --root /tmp/my-project list task --json
wsctl --root /tmp/my-project context --project demo --query 任务 --json
```

## 适配现有工作区

原型提供了一个只读预览命令，把旧工作区映射到新的 `.wsctl/`：

```bash
wsctl legacy preview \
  --source /path/to/old-workspace \
  --out /path/to/preview-workspace \
  --project my-project
```

它不会修改旧工作区。项目、知识、决策和证据会写入预览目录的 `.wsctl/`，并抽取一个演示任务用于验证任务上下文。

## MCP

```bash
wsctl-mcp --list-tools
wsctl-mcp --workspace /path/to/preview-workspace
```

默认所有工作区只读；写入需要在注册时显式开启：

```bash
wsctl workspace add /path/to/project --allow-write
```

## 当前边界

包含：

- workspace 注册表；
- project/task/knowledge/decision/evidence；
- context 与全文检索；
- CLI 和 MCP；
- `wsctl init` 与 legacy preview。

不包含：

- 构建、测试、部署、烧写；
- 外部 SaaS 同步；
- 远程 HTTP 服务；
- 多用户权限系统；
- 自动 Git commit。

