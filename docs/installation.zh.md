# 安装

<!-- auto-updated: version from src/nines/__init__.py -->

NineS {{ nines_version }} 在不同安装方式和环境下的详细安装说明。

---

## 系统要求

| 依赖项 | 最低要求 | 推荐配置 |
|--------|---------|---------|
| Python | 3.12+ | 3.12 |
| 操作系统 | Linux、macOS、Windows | Linux 或 macOS |
| 内存 | 512 MB | 2 GB+ |
| 磁盘空间 | 100 MB | 500 MB（含数据） |

---

## 安装方式

=== "一键脚本（最快）"

    `scripts/install.sh` 脚本一站式处理 Python 版本验证、包安装和智能体技能配置：

    ```bash
    curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
    ```

    如果你已经克隆了仓库：

    ```bash
    bash scripts/install.sh --target all
    ```

    选项:

    | 参数 | 描述 |
    |------|------|
    | `--target <RUNTIME>` | 智能体运行时：`cursor`、`claude`、`codex`、`copilot`、`all`（默认：`all`） |
    | `--global` | 将技能文件安装到用户全局目录 |
    | `--no-skill` | 仅安装 Python 包，跳过技能文件生成 |

=== "uv（推荐）"

    [uv](https://docs.astral.sh/uv/) 提供最快的安装体验。

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    uv sync
    uv run nines --version
    ```

    如需在不使用 `uv run` 前缀的情况下运行 NineS 命令，请激活环境：

    ```bash
    source .venv/bin/activate
    nines --version
    ```

=== "pip（可编辑模式）"

    以可编辑模式安装，适用于开发：

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    pip install -e .
    nines --version
    ```

=== "pip（直接安装）"

    直接从仓库安装：

    ```bash
    git clone https://github.com/YoRHa-Agents/NineS.git
    cd NineS
    pip install .
    nines --version
    ```

---

## 验证安装

安装完成后，验证 NineS 是否正常工作：

```bash
nines --version
# nines, version {{ nines_version }}

nines --help
# 显示所有可用命令
```

---

## 配置文件设置

NineS 使用 TOML 配置，采用基于优先级的合并机制：

1. **CLI 参数** — 覆盖一切（`--config`、`--verbose` 等）
2. **项目配置** — 项目根目录下的 `nines.toml`
3. **用户配置** — `~/.config/nines/config.toml`
4. **内置默认值** — 打包在安装包中

创建项目级配置：

```bash
cat > nines.toml << 'EOF'
[general]
log_level = "INFO"
output_dir = "./reports"

[eval]
default_scorer = "composite"
sandbox_enabled = true

[collect]
default_limit = 50
incremental = true

[analyze]
default_depth = "standard"
decompose = true
index = true
EOF
```

!!! note "配置发现"
    NineS 会自动在当前工作目录或任意父目录中查找 `nines.toml`。

---

## 环境变量

NineS 在运行时读取以下环境变量：

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `NINES_GITHUB_TOKEN` | 用于 V2 采集的 GitHub 个人访问令牌 | `ghp_xxxxxxxxxxxx` |
| `NINES_EVAL_DEFAULT_SCORER` | 覆盖默认评分器 | `composite` |
| `NINES_COLLECT_GITHUB_TOKEN` | GitHub 令牌（别名） | `ghp_xxxxxxxxxxxx` |
| `NINES_GENERAL_LOG_LEVEL` | 覆盖日志级别 | `DEBUG` |

环境变量命名约定：`NINES_<SECTION>_<KEY>`，全部大写，点号替换为下划线。

!!! warning "令牌安全"
    切勿将 API 令牌提交到版本控制系统。请使用环境变量或密钥管理器。令牌字段在日志和错误信息中会被脱敏处理。

---

## 故障排查

### `nines: command not found`

确保安装目录在 `PATH` 中：

```bash
# If using uv
uv run nines --version

# If using pip, check that the scripts directory is on PATH
python -m nines.cli.main --version
```

### Python 版本不匹配

NineS 需要 Python 3.12+。请检查你的版本：

```bash
python --version
```

如果你安装了多个 Python 版本，请指定正确的版本：

```bash
uv venv --python 3.12
uv sync
```

### 权限被拒绝

如果使用 pip 进行全局安装，建议改用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### GitHub API 速率限制

如果采集命令因速率限制而失败：

1. 设置 GitHub 个人访问令牌：
   ```bash
   export NINES_GITHUB_TOKEN="ghp_your_token_here"
   ```
2. 令牌提供每小时 5,000 次请求（未认证为 60 次）
3. NineS 会通过自适应退避自动处理速率限制

### SQLite 错误

如果遇到数据库错误：

```bash
# Reset the database
rm -f data/nines.db
nines collect github "test" --limit 1  # Recreates the schema
```
