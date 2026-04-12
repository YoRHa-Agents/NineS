# 贡献指南

<!-- auto-updated: version from src/nines/__init__.py -->

感谢您为 NineS 做出贡献！本指南涵盖开发环境设置、测试、代码风格和 PR 工作流。

---

## 开发环境设置

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- Git

### 克隆和安装

```bash
git clone https://github.com/YoRHa-Agents/NineS.git
cd NineS
uv sync
```

这会以可编辑模式安装 NineS 及所有开发依赖（pytest、ruff、mypy）。

### 验证设置

```bash
make test      # 运行所有测试
make lint      # 检查代码风格
make typecheck # 运行类型检查
```

---

## 运行测试

NineS 使用 pytest，测试结构如下：

```
tests/
├── conftest.py              # 共享 fixtures、临时目录、mock 工厂
├── test_core_*.py           # Core 模块测试
├── test_eval_*.py           # 评估测试
├── test_collector_*.py      # Collector 测试
├── test_analyzer_*.py       # Analyzer 测试
├── test_iteration_*.py      # 自迭代测试
├── test_sandbox_*.py        # 沙箱测试
├── test_skill_*.py          # Skill 适配器测试
├── test_cli_*.py            # CLI 命令测试
└── integration/
    ├── test_eval_e2e.py     # 端到端评估
    ├── test_collect_analyze.py
    ├── test_iteration_cycle.py
    └── test_sandbox_isolation.py
```

### 运行所有测试

```bash
make test
```

### 运行特定测试

```bash
# 运行单个测试文件
uv run pytest tests/test_eval_runner.py -v

# 运行匹配模式的测试
uv run pytest -k "test_scorer" -v

# 带覆盖率运行
make coverage
```

### 测试覆盖率报告

```bash
make coverage
# 生成 htmlcov/index.html
```

!!! note "强制验证"
    所有新功能和 bug 修复必须包含测试。禁止跳过或标记测试为 "todo" 以绕过覆盖率要求。

---

## 代码风格

NineS 通过 [ruff](https://docs.astral.sh/ruff/) 强制一致的代码风格：

### 代码检查

```bash
make lint
```

启用的 ruff 规则集：

| 规则集 | 描述 |
|--------|------|
| E | pycodestyle 错误 |
| F | pyflakes |
| W | pycodestyle 警告 |
| I | isort（import 排序） |
| N | pep8-naming |
| UP | pyupgrade |
| B | flake8-bugbear |
| A | flake8-builtins |
| SIM | flake8-simplify |
| TCH | flake8-type-checking |

### 格式化

```bash
make format
```

配置（`pyproject.toml`）：

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.format]
quote-style = "double"
```

### 类型检查

```bash
make typecheck
```

NineS 使用严格模式的 `mypy`：

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

---

## PR 工作流

### 分支命名

使用描述性的分支名称：

```
feature/add-semantic-search
fix/sandbox-pollution-detection
docs/update-architecture-overview
refactor/eval-runner-pipeline
```

!!! warning "受保护分支"
    禁止直接推送到 `main`、`master`、`yc_dev` 或 `production`。请始终创建功能分支并提交 PR/MR。

### 提交消息

遵循约定式提交风格：

```
feat: add semantic search to knowledge index
fix: resolve sandbox env var leak in pollution detector
docs: update CLI reference with new iterate options
refactor: extract scorer registry from eval runner
test: add integration tests for MAPIM cycle
```

### PR 检查清单

提交 PR 前请确认：

- [ ] 所有测试通过（`make test`）
- [ ] 代码检查通过（`make lint`）
- [ ] 类型检查通过（`make typecheck`）
- [ ] 新代码包含测试
- [ ] 如果行为变更则更新文档
- [ ] 无静默失败——每个 `except` 块都记录日志或重新抛出

### 审查流程

1. 从 `main` 创建功能分支
2. 编写变更和测试
3. 推送并创建 PR
4. 回应审查反馈
5. 保持 CI 检查通过
6. 批准后合并

---

## 模块所有权

贡献特定模块时，请了解其依赖规则：

| 模块 | 可以导入 | 不可导入 |
|------|---------|---------|
| `core/` | （无） | 其他所有模块 |
| `eval/` | `core/` | `collector/`、`analyzer/`、`iteration/` |
| `collector/` | `core/` | `eval/`、`analyzer/`、`iteration/` |
| `analyzer/` | `core/` | `eval/`、`collector/`、`iteration/` |
| `iteration/` | `core/`、`eval/` | `collector/`、`analyzer/` |
| `orchestrator/` | 所有顶点模块、`core/` | `cli/`、`skill/` |
| `sandbox/` | `core/` | 其他所有模块 |
| `skill/` | `core/` | 其他所有模块 |
| `cli/` | 所有模块 | （无——组合根） |

---

## 错误处理指南

NineS 执行严格的"无静默失败"策略：

1. **禁止裸 `except: pass`** — 每个捕获的异常必须被记录、重新抛出或产生明确的错误状态
2. **使用类型化异常** — 所有错误继承自 `NinesError`，包含结构化字段（`code`、`message`、`hint`）
3. **逐项隔离** — 单个任务/文件的失败不应中止批量操作
4. **重试瞬态错误** — HTTP 429/500/502/503 最多重试 3 次，使用指数退避

---

## Make 目标

| 目标 | 描述 |
|------|------|
| `make test` | 使用 pytest 运行所有测试 |
| `make lint` | 运行 ruff 代码检查 |
| `make format` | 使用 ruff 自动格式化 |
| `make typecheck` | 运行 mypy 严格类型检查 |
| `make coverage` | 生成测试覆盖率报告 |
| `make clean` | 清理构建产物和缓存 |
