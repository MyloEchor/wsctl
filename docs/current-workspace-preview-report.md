# 当前工作区适配预演报告

日期：2026-10-08

## 预演方式

使用外部原型仓库 `wsctl` 的 `legacy preview` 命令读取当前工作区：

```bash
wsctl legacy preview \
  --source /home/cj/buildroot-workspace-framework \
  --out examples/current-workspace-preview \
  --project echolife-rk3576
```

源工作区只读，未修改。

## 映射结果

| 对象 | 数量 |
|---|---:|
| 项目 | 1 |
| 知识 | 30 |
| 决策 | 8 |
| 证据 | 32 |
| 演示任务 | 1 |
| 索引文档 | 71 |

映射关系：

- `management/projects.yaml` 和 `products/*/project.yaml` -> `.wsctl/projects/`
- `knowledge/**/*.md` -> `.wsctl/knowledge/`
- `knowledge/adr/ADR-*.md` -> `.wsctl/decisions/`
- `products/<project>/evidence/*.md` -> `.wsctl/evidence/`
- 平台、Profile、测试档位、Board Profile -> 项目 `legacy` 元数据

## 验证结果

- `.venv` 可编辑安装成功；
- `wsctl doctor` 通过，错误 0，警告 0；
- `wsctl projects list` 能读出 `echolife-rk3576`；
- `wsctl list task` 能读出生成任务和 MCP 冒烟任务；
- `wsctl search "AB 槽位"` 能命中知识与证据；
- `wsctl context` 能组合项目、知识、决策和证据，并返回有界摘要；
- `wsctl-mcp --list-tools` 注册 15 个工具；
- MCP `workspace_info`、`create_task`、`task_list` 冒烟通过；
- 写入权限验证：只有注册时 `--allow-write` 的 workspace 允许 MCP 写入。

## 已发现并修正的问题

1. FTS5 `unicode61` 对无空格中文检索不稳定，增加子串回退。
2. 项目上下文最初排除了无 `project` 字段的全局知识和决策，已改为同时纳入项目级与全局对象。
3. 初始 context 返回完整证据正文，体积过大，已改为只返回摘要和 `excerpt`。
4. MCP Python SDK 2.x 移除了原型使用的 `FastMCP` 接口，因此当前依赖明确 pin 到 `mcp>=1.0,<2`。

## 适配结论

适配良好的部分：

- 项目注册与元数据；
- 知识、决策、证据的 Git 友好存储；
- Agent 上下文聚合；
- 多工作区注册与 MCP 调用；
- 默认只读、显式允许写入的安全边界；
- 文件写入与 Git 提交分离。

不适合进入通用核心的部分：

- `west.yml` 的源码 SHA 身份锁；
- `platforms/` / `products/` 物理布局；
- Buildroot 构建阶段；
- 板卡、槽位、烧写和审批；
- 当前仓库的长期开发线与承载仓规则。

这些能力可以作为当前工作区的专用适配器或独立 CLI，继续留在原仓库，不应成为开源核心的默认模型。

