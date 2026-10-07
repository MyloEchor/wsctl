# 旧工作区适配预览

`wsctl legacy preview` 读取旧工作区的管理数据，生成一个新的 `.wsctl/` 预览目录。

映射关系：

| 旧结构 | 新结构 |
|---|---|
| `management/projects.yaml` | `.wsctl/projects/*.yaml` |
| `knowledge/**/*.md` | `.wsctl/knowledge/*.md` |
| `knowledge/adr/ADR-*.md` | `.wsctl/decisions/*.md` |
| `products/<project>/evidence/*.md` | `.wsctl/evidence/*.md` |
| project `test_tiers` / `profiles` | project `legacy` 元数据 |

该命令只读源目录，不修改原工作区。

