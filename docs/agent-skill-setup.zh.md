# 智能体技能安装

<!-- auto-updated: version from src/nines/__init__.py -->

NineS 可作为智能体技能安装到 Cursor、Claude Code、Codex 或 GitHub Copilot 中，使 AI 编程助手能够直接在 IDE 中使用 NineS 的各项能力。

---

## 什么是智能体技能？

智能体技能是一组指令和命令定义，用于教会 AI 编程助手如何使用工具。安装后：

- **Cursor** 会读取 `.cursor/skills/nines/SKILL.md` 和各命令的工作流文件
- **Claude Code** 会读取 `.claude/commands/nines/*.md` 斜杠命令和 `CLAUDE.md` 上下文
- **Codex** 会读取 `.codex/skills/nines/SKILL.md` 和各命令的工作流文件
- **GitHub Copilot** 会读取 `.github/copilot-instructions.md` 中的能力上下文

该技能使 AI 助手能够代替你运行评估、采集信息、分析代码库以及执行自我改进迭代。

---

## 一键安装

安装 NineS 并为所有运行时设置技能文件的最快方式：

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
```

或指定特定目标运行时：

```bash
bash scripts/install.sh --target cursor
bash scripts/install.sh --target codex
bash scripts/install.sh --target copilot
bash scripts/install.sh --target all
```

安装脚本会一步完成 Python 版本检查、包安装和技能文件生成。

---

## 运行时兼容性

| 运行时 | 目标参数 | 安装目录 | 技能格式 | 最低版本 |
|--------|---------|---------|---------|---------|
| Cursor | `cursor` | `.cursor/skills/nines/` | `SKILL.md` + 命令工作流 | 0.50.0 |
| Claude Code | `claude` | `.claude/commands/nines/` | 斜杠命令 + `CLAUDE.md` | 1.0.0 |
| Codex | `codex` | `.codex/skills/nines/` | `SKILL.md` + 命令工作流 | — |
| GitHub Copilot | `copilot` | `.github/copilot-instructions.md` | 单指令文件 | — |

---

## 为 Cursor 安装

```bash
nines install --target cursor
```

此命令会在你的项目中创建以下结构：

```
.cursor/
└── skills/
    └── nines/
        ├── SKILL.md              # Main skill entry point
        ├── manifest.json         # Version manifest
        ├── commands/
        │   ├── eval.md           # nines eval workflow
        │   ├── collect.md        # nines collect workflow
        │   ├── analyze.md        # nines analyze workflow
        │   ├── self-eval.md      # nines self-eval workflow
        │   ├── iterate.md        # nines iterate workflow
        │   └── install.md        # nines install workflow
        └── references/
            ├── capabilities.md   # Capability model reference
            └── config.md         # Configuration reference
```

安装完成后，在 Cursor 中提及任何 NineS 命令（例如 "run nines eval on my tasks"），助手就会读取技能工作流并执行。

---

## 为 Claude Code 安装

```bash
nines install --target claude
```

此命令会创建斜杠命令并更新 `CLAUDE.md`：

```
.claude/
└── commands/
    └── nines/
        ├── eval.md
        ├── collect.md
        ├── analyze.md
        ├── self-eval.md
        ├── iterate.md
        ├── install.md
        └── manifest.json
```

同时会在 `CLAUDE.md` 中追加 NineS 使用上下文。使用 `/nines:eval`、`/nines:collect` 等命令即可。

---

## 为 Codex 安装

```bash
nines install --target codex
```

此命令会在你的项目中创建以下结构：

```
.codex/
└── skills/
    └── nines/
        ├── SKILL.md              # 主技能入口
        ├── manifest.json         # 版本清单
        └── commands/
            ├── eval.md           # nines eval 工作流
            ├── collect.md        # nines collect 工作流
            ├── analyze.md        # nines analyze 工作流
            ├── self-eval.md      # nines self-eval 工作流
            ├── iterate.md        # nines iterate 工作流
            └── install.md        # nines install 工作流
```

安装完成后，Codex 可以通过技能入口发现并调用 NineS 命令。

---

## 为 GitHub Copilot 安装

```bash
nines install --target copilot
```

此命令会创建一个指令文件：

```
.github/
└── copilot-instructions.md     # Copilot 的 NineS 能力文档
```

GitHub Copilot 读取 `.github/copilot-instructions.md` 来了解 NineS 命令和能力。该文件记录了所有可用的 CLI 命令及其使用模式。

---

## 为所有运行时安装

一次性为所有检测到的运行时安装：

```bash
nines install --target all
```

NineS 会通过检查 `.cursor/`、`.claude/`、`.codex/` 或 `.github/` 目录以及 `$PATH` 中的运行时可执行文件来自动检测可用运行时。

---

## 全局安装

将技能全局安装（适用于所有项目）：

```bash
nines install --target cursor --global
```

全局安装会写入 `~/.cursor/skills/nines/`、`~/.claude/commands/nines/`、`~/.codex/skills/nines/` 或 `~/.github/copilot-instructions.md`。

---

## 验证技能是否已激活

### Cursor

1. 打开已安装技能的项目
2. 向助手提问："What NineS commands are available?"
3. 助手应列出 SKILL.md 中的全部六个命令

### Claude Code

1. 在 Claude Code 提示符中输入 `/nines:`
2. 自动补全应显示可用的 NineS 命令
3. 运行 `/nines:self-eval --report` 进行测试

### Codex

1. 打开已安装技能的项目
2. 向助手提问："What NineS commands are available?"
3. 助手应列出 SKILL.md 中的所有命令

### GitHub Copilot

1. 打开存在 `.github/copilot-instructions.md` 的项目
2. 向 Copilot 提问："How do I run NineS evaluations?"
3. Copilot 应引用 NineS CLI 命令和使用模式

---

## 版本升级时更新技能

当你将 NineS 更新到新版本时，重新运行安装命令：

```bash
pip install -e .  # or uv sync
nines install --target cursor
```

NineS 会检测到现有安装并执行原地升级。`manifest.json` 中的版本号会自动更新。

!!! tip "试运行"
    在不写入文件的情况下预览安装或升级将执行的操作：
    ```bash
    nines install --target cursor --dry-run
    ```

---

## 卸载

从特定运行时移除 NineS 技能：

```bash
nines install --target cursor --uninstall
```

从所有运行时移除：

```bash
nines install --target all --uninstall
```

对于 Claude Code，此操作还会移除 `CLAUDE.md` 中的 NineS 部分。

---

## 版本管理

| 场景 | 行为 |
|------|------|
| 全新安装 | 创建所有文件 |
| 相同版本 | 跳过并提示（使用 `--force` 强制重新安装） |
| 升级 | 原地更新所有文件 |
| 降级 | 默认阻止（使用 `--force` 强制覆盖） |
