# 采集指南 (V2)

<!-- auto-updated: version from src/nines/__init__.py -->

NineS V2 可发现、获取、存储和追踪与 AI 代理研究相关的外部信息源。支持 GitHub 仓库和 arXiv 论文，具备增量采集和结构化变更检测能力。

---

## 支持的数据源

| 数据源 | API | 数据类型 | 速率限制 |
|--------|-----|---------|---------|
| **GitHub** | REST v3 + GraphQL v4 | 仓库、发布版本、提交、贡献者 | 搜索: 30 次/分钟, 核心: 5,000 次/小时 |
| **arXiv** | Atom XML API | 论文、元数据、版本历史 | 1 次/3 秒 |

---

## 搜索与采集命令

### GitHub 搜索

```bash
# 基本搜索
nines collect github "AI agent evaluation" --limit 20

# 按语言和星标数筛选
nines collect github "LLM benchmark" --limit 50

# 增量模式（仅获取上次运行后的新项目）
nines collect github "AI agent evaluation" --incremental --store ./data/collections
```

GitHub 搜索会将您的查询转换为 GitHub 搜索限定符。获取的元数据包括：星标数、Fork 数、语言、主题标签、README 内容、近期提交和发布版本。

### arXiv 搜索

```bash
# 基本搜索
nines collect arxiv "LLM self-improvement" --limit 10

# 按类别搜索
nines collect arxiv "agent evaluation" --limit 20
```

arXiv 查询支持标题（`ti:`）、作者（`au:`）、摘要（`abs:`）和类别（`cat:`）前缀。默认类别：`cs.AI`、`cs.SE`、`cs.CL`、`cs.LG`。

---

## 增量追踪

增量模式仅获取自上次采集运行以来新增或变更的项目：

```bash
nines collect github "AI agent evaluation" --incremental
```

追踪器为每个数据源项目维护书签：

| 数据源 | 书签内容 | 变更检测方式 |
|--------|---------|-------------|
| GitHub | ETag、`pushed_at` 时间戳、星标数 | HTTP 条件请求（304 Not Modified） |
| arXiv | `updated_at` 时间戳、论文版本号 | 内容指纹对比 |

过期启发式规则根据活跃度自适应调整刷新间隔：

- **活跃仓库**（7 天内有推送）：15 分钟刷新
- **不活跃仓库**：24 小时刷新
- **arXiv 论文**：6 小时刷新（arXiv 每日更新）

---

## 变更检测

NineS 检测并分类采集快照之间的变更：

```bash
# 查看近期变更
nines collect status
```

### 变更类别

| 变更模式 | 类别 | 重要程度 |
|---------|------|---------|
| 发布新版本 | `feature` | 高 |
| 星标数变化 >20% | `metrics` | 高 |
| 仓库已归档 | `breaking` | 高 |
| 论文版本更新 | `feature` | 高 |
| README 内容变更 | `docs` | 中 |
| 星标数变化 ≤20% | `metrics` | 低 |
| 主题标签变更 | `docs` | 低 |

---

## 数据存储（SQLite）

所有采集的数据均存储在 SQLite 中，支持全文搜索：

```bash
# 默认位置
data/nines.db

# 通过配置覆盖
[collect]
store_path = "./data/my_collection.db"
```

### 存储结构

- **`repositories`** — GitHub 仓库，包含元数据、指标和 JSON 子数据
- **`papers`** — arXiv 论文，包含作者、类别和摘要
- **`collection_snapshots`** — 带指纹的时间点状态快照
- **`change_events`** — 快照之间的结构化差异
- **`tracking_bookmarks`** — 增量采集的游标状态
- **`response_cache`** — 基于 TTL 的响应缓存

全文搜索（FTS5）已在仓库名称、描述、README 内容、论文标题、摘要和作者上启用。

### 导出

```bash
# 导出为 JSON
nines collect export --format json -o repos.json

# 导出为 Markdown
nines collect export --format markdown -o repos.md
```

---

## 调度

通过刷新间隔配置定期采集：

```toml
[collect.tracking]
default_refresh_interval = "24h"
```

| 数据源 | 默认间隔 | 备注 |
|--------|---------|------|
| GitHub 追踪项 | 1 小时 | 高活跃仓库通过过期启发式规则获得 15 分钟间隔 |
| arXiv 类别 | 6 小时 | arXiv 每日更新 |

手动完全刷新：

```bash
nines collect github "query" --no-incremental
```

---

## 认证

### GitHub 令牌

设置 GitHub 个人访问令牌以获得更高的速率限制（5,000 次/小时 vs. 60 次）：

```bash
export NINES_GITHUB_TOKEN="ghp_your_token_here"
```

或在 `nines.toml` 中配置：

```toml
[collect.github]
token = "ghp_your_token_here"  # prefer env var
```

令牌解析顺序：

1. `NINES_GITHUB_TOKEN` 环境变量
2. `NINES_COLLECT_GITHUB_TOKEN` 环境变量
3. `nines.toml` 配置值
4. `gh auth token` 输出（GitHub CLI 回退）

!!! example "速率限制"
    NineS 使用按 API 层级校准的令牌桶速率限制器。当接近限制（剩余 < 10%）时，会自动将请求间隔加倍。HTTP 429 响应会使用 `retry-after` 头触发退避机制。
