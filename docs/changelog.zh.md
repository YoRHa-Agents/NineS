# 变更日志

NineS 的所有重要变更均记录于此。本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

---

## v3.0.0 — 2026-04-14

**主题：** 知识图谱分析引擎 — 整合 [Understand-Anything](https://github.com/Lum1104/Understand-Anything) 的仓库分解与分析能力，构建完整的分析→分解→验证→总结核心能力。

> 破坏性变更：新增 `graph` 分解策略，自评扩展至 24 维度，分析管道支持多语言扫描和知识图谱构建。

### 新增
- **多语言项目扫描器** (`scanner.py`) — 支持 30+ 编程语言的文件发现、语言检测、类别分类（code/config/docs/infra/data/script/markup），以及框架检测
- **跨语言导入图构建器** (`import_graph.py`) — 基于 AST（Python）和正则（JS/TS/Go/Rust）的项目内部依赖图构建
- **知识图谱数据模型** (`graph_models.py`) — `GraphNode`、`GraphEdge`、`ArchitectureLayer`、`KnowledgeGraph`、`VerificationResult`、`AnalysisSummary` 等完整类型化模型
- **图谱分解策略** (`graph_decomposer.py`) — 新增 `--strategy graph` 选项，构建含类型化节点/边/层的完整知识图谱
- **图谱验证器** (`graph_verifier.py`) — 引用完整性、重复边、孤立节点、层覆盖率、类型合法性等 7 项检查
- **分析摘要生成器** (`summarizer.py`) — 从知识图谱生成结构化摘要，含 fan-in/fan-out 排名、入口点检测、Agent 影响文本
- **4 个新自评维度** (D21-D24):
  - `graph_decomposition_coverage` (D21) — 图谱文件覆盖率
  - `graph_verification_pass_rate` (D22) — 图谱结构完整性
  - `layer_assignment_quality` (D23) — 架构层分配质量
  - `summary_completeness` (D24) — 摘要完整性
- **分析管道 `graph` 策略集成** — `nines analyze --strategy graph` 自动执行：扫描→导入图→知识图谱→验证→摘要
- **CLI 图谱输出** — `nines analyze` 文本报告新增知识图谱统计信息（扫描文件、语言、框架、导入边、图节点/边/层、验证结果）
- 新增 67 项测试（总计 1189 项）

### 设计决策
- **确定性优先，LLM 辅助** — 借鉴 Understand-Anything 的两阶段设计（脚本先行→LLM 补充），所有核心逻辑基于 AST/正则/路径启发式，不依赖 LLM
- **类型化图谱合约** — 节点类型（11 种）、边类型（10 种）、文件类别（7 种）均有 `frozenset` 约束，验证器强制检查
- **路径 + Fan-in 混合层分配** — 结合路径模式匹配和 fan-in 排名提升，高依赖节点自动归入核心层
- **一切为 Agent 能力验证服务** — 自评维度 D21-D24 直接度量图谱分解与验证质量，驱动迭代改进

### 改进
- **自评从 20 维扩展至 24 维** — D21-D24 覆盖图谱分解、验证、层分配、摘要
- **分析管道新增组件注入** — `AnalysisPipeline.__init__` 支持注入 `scanner`、`graph_decomposer`、`graph_verifier`、`summarizer`
- **`analyzer/__init__.py` 公开 API 扩展** — 导出所有新模块的公开类
- **全量测试**: 1189 项通过，0 个 lint 错误

---

## v2.1.0 — 2026-04-14

**主题：** 自更新迭代 — 分析质量改进、策略路由、参考体系，由 DevolaFlow self-update 工作流驱动，分析 [Understand-Anything](https://github.com/Lum1104/Understand-Anything) 仓库。

### 新增
- **分解策略路由** — `--strategy concern|layer|functional` 现在正确调度至对应的 `Decomposer` 方法（此前硬编码为 `functional`）
- **指标中记录策略和深度** — 分析结果的 metrics 中包含 `strategy` 和 `depth` 字段
- **参考体系** — `references/` 目录下 6 篇 DevolaFlow 风格参考文档，含 YAML 前置元数据
- **SKILL.md 参考导航指南** — 快速参考表，支持按需加载上下文
- **关键点语义去重** — 同类别内描述词重叠 >60% 的关键点自动合并
- 新增 27 项测试（总计 1093 项）

### 修复
- **Finding ID 冲突** — ID 现包含基于文件路径的确定性哈希前缀（`CC-{hash}-{idx}`），消除多文件分析时的重复 ID（修复前：Understand-Anything 仓库有 10 个重复 ID）
- **有益机制影响判断** — `behavioral_instruction`、`safety`、`persistence` 机制正确归类为 `"positive"` 影响（修复前：因仅凭 token 数量判断而误标为 `"negative"`）
- **影响幅度饱和** — 从线性公式改为对数尺度（`log1p`），产生可区分的幅度值（修复前：>5K token 全部为 1.0；修复后：0.817–0.862 区间）
- **arxiv 收集器** — `_DEFAULT_BASE_URL` 从 `http://` 升级为 `https://`

### 改进
- **Understand-Anything 分析**: 0 个重复 Finding ID、5 个可区分的机制幅度、3 个正确标记为 positive 的有益机制
- **全量测试**: 1093 项通过，0 个 lint 错误

---

## v2.0.0 — 2026-04-13

**主题：** 面向 Agent 的仓库分析重新对齐 — NineS 现在是专门分析仓库如何提升 AI Agent 效能的工具。

> 破坏性变更：分析管道默认值变更，自评扩展至 20 维度，基准执行器替换。

### 新增
- **AgentAnalysisQualityEvaluator (D20)** — 衡量 NineS 检测制品、机制、经济学、发现和关键点的能力
- **SourceFreshnessEvaluator (D07)** — 在可配置窗口内检测数据新鲜度（默认 30 天）
- **ChangeDetectionEvaluator (D08)** — 验证 DataStore 更新检测能力
- **真实基准执行器** — 按维度比较评分替代直通执行器（压缩、上下文、行为、语义、跨平台、工程）
- **`ingest_all()` 方法** — 发现非 Python Agent 制品（.yaml, .md, .json, .toml 等）
- **`nines benchmark --tasks-path`** — 加载自定义 TOML 任务定义
- **`nines iterate --project-root/--src-dir/--test-dir`** — 实时评估器支持
- **可配置 `cov_package`** 和 **覆盖率文件解析**（coverage.xml/json）
- **pytest --collect-only** 精确计数测试，AST 遍历降级
- 新增 13 个测试（总计 1069）

### 变更
- **[破坏性] `nines analyze` 默认启用 Agent 影响分析** — `--agent-impact/--no-agent-impact` 标志对
- **[破坏性] `nines analyze` 默认启用关键点提取** — `--keypoints/--no-keypoints` 标志对
- **[破坏性] 基准执行器** 产出差异化评分（均值 0.4）替代直通 1.0
- **自评从 17 维扩展至 20 维**（D07、D08、D20）
- **Context Economics 增强** — 含机制 token 开销、扩展制品模式、最低估算回退
- **KeyPointExtractor** 过滤通用指标噪声 — 23→10 关键点，工程观察限 5 个
- **`nines iterate`** 注册全部 20 个能力维度 + 5 个卫生维度
- **README** 重写：Agent 仓库分析使命，修复所有 CLI 示例
- **SKILL.md** 重写：核心工作流描述

### 改进
- **自评总分：0.9727** — 20 维度，D07=50%（真实新鲜度信号），D20=100%
- **基准均分：0.4** — 跨维度真实分化
- **Context Economics**：overhead=3575 tokens, savings=15%, breakeven=7 次交互
- **Agent 影响关键点**：9/10 面向 Agent（原 9/23）

---

## v1.1.0 — 2026-04-13

**主题：** 外部项目支持与 DevolaFlow 集成反馈修复。

> 基于 DevolaFlow v4.3.1 的集成测试反馈，本版本修复了 NineS 在评估外部项目时的 4 个核心问题，使 NineS 从「只能评估自身」变为「可以评估任意 Python 项目」的通用工具。

### 新增
- **`LiveCodeCoverageEvaluator` 可配置覆盖包名** — 新增 `cov_package` 参数，替代硬编码的 `--cov=nines`，评估外部项目（如 DevolaFlow）时可正确测量覆盖率
- **覆盖率文件解析** — 新增 `coverage_file` 参数，支持直接读取 `coverage.xml`（Cobertura 格式）和 `coverage.json` 文件，无需重新执行 pytest
- **`LiveTestCountEvaluator` 优先使用 pytest 收集** — 采用 `pytest --collect-only -q` 精确计数（含参数化测试、类方法测试等），AST 遍历作为降级回退
- **`nines iterate` 项目上下文标志** — 新增 `--project-root`、`--src-dir`、`--test-dir`，支持自动检测源码和测试目录
- **`nines iterate` 实时评估器** — 指定 `--project-root` 后使用 5 个实时评估器（覆盖率、测试数、模块数、文档字符串覆盖率、Lint 清洁度），替代固定 0 值的桩评估器
- **`nines benchmark --tasks-path`** — 新增自定义 TOML 任务目录选项，跳过自动生成的通用任务，直接加载用户定义的项目特定基准测试任务
- 新增 24 个测试用例（self_eval: 6, iterate_cmd: 14, benchmark_cmd: 4），总测试数达 1052

### 变更
- `LiveCodeCoverageEvaluator` 元数据新增 `source` 字段（`"file"` 或 `"pytest"`），标明覆盖率数据来源
- `LiveTestCountEvaluator` 元数据新增 `method` 字段（`"pytest-collect"` 或 `"ast-walk"`），标明计数方法
- `nines iterate` 无 `--project-root` 时输出警告并使用非零桩值（避免立即收敛至 0.0）
- `nines iterate` 修复 `conv_result` 潜在未绑定变量错误

### 改进
- **自评分数：0.9928** — 能力维度 17/17 全部 100%，卫生 97.6%（覆盖率 90%，测试 1052，模块 65，文档 100%，Lint 98%）
- NineS 现可作为通用项目质量扫描器，不再局限于评估自身
- DevolaFlow 集成场景下，`nines iterate --project-root .` 可正确产出 0.976 的综合分数

---

## v1.0.0 — 2026-04-13

**主题：** 多运行时技能集成、19 维度能力评估与生产就绪。

### 新增
- **Codex 适配器** — 将 NineS 安装为 Codex 技能至 `.codex/skills/nines/`，包含 SKILL.md 及命令工作流文件
- **GitHub Copilot 适配器** — 将 NineS 安装为 Copilot 指令至 `.github/copilot-instructions.md`
- **一键安装脚本** (`scripts/install.sh`) — `curl | bash` 风格安装器，支持 Python 检测、uv/pip 自动回退及技能文件自动生成
- **`--uninstall` CLI 标志** — `nines install` 支持从任意目标运行时清除技能文件
- **DevolaFlow 集成反馈** — 提议 NineS 作为 DevolaFlow v4.2.0 的质量门控评分器、研究工具和顾问插件
- 新增 12 个测试用例覆盖 Codex 适配器、Copilot 适配器、安装器集成和卸载流程
- **19 维度能力评估框架** — 设计文档中所有维度 (D01–D19) 均已接入实时评估器
- **V1 评估评估器**（D01 评分准确性、D03 可靠性、D05 评分器一致性）配合 20 个 golden 测试任务
- **V2 采集评估器**（D06 数据源覆盖、D09 数据完整性、D10 采集吞吐量）
- **V3 分析评估器**（D11–D15）度量分解覆盖、抽象质量、代码审查准确性、索引召回、结构识别
- **系统评估器**（D16 管道延迟、D17 沙箱隔离、D18 收敛率、D19 跨顶点协同）
- Golden 测试集位于 `data/golden_test_set/`，包含 20 个校准 TOML 任务
- 自评 CLI 重构：能力 70% / 卫生 30% 加权，按 V1/V2/V3/System 分组输出
- 新增 `--capability-only` 和 `--golden-dir` CLI 选项（总计：1005 个测试）

### 变更
- `nines install --target` 现支持 5 个目标：`cursor`、`claude`、`codex`、`copilot`、`all`
- 安装器 `ADAPTERS` 注册表从 2 个运行时扩展到 4 个
- Skill `__init__.py` 公开 API 新增 `CopilotAdapter`

### 改进
- **自评分数：0.9940** — 17/17 能力维度达到 100%，卫生 98%
  - V1 评估：D01–D05 全部 100%（评分准确性、覆盖率、可靠性、报告质量、评分器一致性）
  - V2 采集：D06/D09/D10 全部 100%（数据源覆盖、数据完整性、吞吐量）
  - V3 分析：D11–D15 全部 100%（分解、抽象、代码审查、索引召回、结构识别）
  - 系统：D16–D19 全部 100%（管道延迟、沙箱隔离、收敛率、跨顶点协同）
- 所有 4 个运行时目标的文档已更新（中英文）
- Agent 技能设置指南、快速入门、CLI 参考、安装指南和设计规范均已反映 v1.0.0-pre 的能力
- README 更新为一键安装及 4 运行时支持

---

## v0.6.0 — 2026-04-13

**主题：** DevolaFlow 分析示例展示与 EvoBench 评测集成。

### 新增
- DevolaFlow 仓库深度分析示例展示 — 15 个关键点、30 个基准测试任务、多轮评测与 EvoBench 维度映射
- EvoBench 集成洞察章节，记录 32 个评估维度（T1–T8、M1–M8、W1–W8、TT1–TT8）与面向 Agent 分析的对齐
- 示例展示报告中新增 NineS 能力评估和 v0.6.0 改进路线图
- DevolaFlow 分析示例展示的中文翻译

### 变更
- 示例展示索引更新，将 DevolaFlow 作为第二个案例研究与 Caveman 并列展示
- 分析方法论扩展至元框架评估（编排规则，而非仅工具）

### 改进
- NineS 评测管道能力和已识别差距的文档完善
- 建立跨仓库分析模式（简单工具 → 元框架）

---

## v0.5.0 — 2026-04-12

**主题：** 可执行评测框架与自驱提升能力。

### 新增
- 关键点提取模块（`KeyPointExtractor`）——将 Agent 影响报告分解为分类、排序的关键点清单，含验证方法
- 基准测试生成模块（`BenchmarkGenerator`）——从关键点生成 `TaskDefinition` 基准测试套件，含按类别的任务模板
- 多轮评测运行器（`MultiRoundRunner`）——沙箱化多轮评测，支持收敛检测和可靠性指标（pass@k、一致性）
- 关键点 → 结论映射模块（`MappingTableGenerator`）——将关键点映射到有效性结论，含置信度和建议
- 五个实时自评估器：`LiveCodeCoverageEvaluator`、`LiveTestCountEvaluator`、`LiveModuleCountEvaluator`、`DocstringCoverageEvaluator`、`LintCleanlinessEvaluator`
- 新 CLI 命令 `nines benchmark`——完整的分析→基准测试→评测→映射工作流
- `nines analyze` 新增 `--agent-impact` 和 `--keypoints` 选项
- `nines self-eval` 新增 `--project-root`、`--src-dir`、`--test-dir` 选项
- 18 个新集成测试，覆盖基准测试工作流和增强型分析流水线
- `BenchmarkSuite` 支持 TOML 目录导出（`to_toml_dir()`）
- `MappingTable` 支持 Markdown 和 JSON 导出
- `MultiRoundReport` 支持逐任务汇总统计

### 变更
- Caveman 示例展示完全重写，演示 v0.5.0 可执行评测方法论——关键点、基准测试、多轮结果、映射表、经验教训
- `AnalysisPipeline.run()` 现接受 `agent_impact` 和 `keypoints` 关键字参数
- 自评估 CLI 使用实时评估器替代占位零值
- 编排器 `Pipeline` 方法现接入真实组件调用（评估、分析、基准测试）
- `nines analyze` CLI 新增 `--depth` 选项

### 改进
- 自评估基于项目内省产生真实测量值（覆盖率、测试计数、文档字符串、代码规范检查）
- 分析流水线将 `AgentImpactAnalyzer` 和 `KeyPointExtractor` 集成到主流程
- 914+ 测试，全面覆盖所有新模块

---

## v0.4.0 — 2026-04-12

**主题：** 面向 Agent 的分析与 AI 仓库评估。

### 新增
- Agent 影响分析模块（`AgentImpactAnalyzer`），评估仓库如何影响 AI Agent 效能
- 新数据模型：`AgentMechanism`、`ContextEconomics`、`AgentImpactReport`，支持完整序列化
- AI 化仓库分析方法的研究综合文档
- Agent 制品检测，涵盖 7 个 AI Agent 平台的 14+ 种模式
- 机制分解，支持 5 种检测类别：行为指令、上下文压缩、安全、分发、持久化
- 上下文经济学估算，包含 Token 开销、节省比率和损益平衡分析
- 45 个新测试用于 Agent 影响分析器，100% 通过率

### 变更
- Caveman 示例展示完全重写为面向 Agent 的分析 — 机制分解、上下文经济学、语义保留、行为影响分析
- 示例展示索引更新，反映面向 Agent 的分析能力
- 分析模块导出扩展，增加 Agent 影响类型

### 改进
- V3 分析现支持双轨模式：传统代码分析 + Agent 影响分析
- AI 仓库评估方法论的文档覆盖

---

## v0.3.0 — 2026-04-12

**主题：** 文档完善与国际化优化。

### 新增
- 开发计划文档，采用与 MAPIM 对齐的工程方法论
- Caveman 仓库分析示例展示，演示 V3 分析能力
- 示例任务文件，便于快速体验评估功能

### 修复
- 中文站点 i18n 问题：语言切换器、导航翻译和 UI 语言设置
- 部署工作流更新 i18n 插件依赖

### 改进
- 重构导航结构，展示设计文档、研究报告和内部参考资料
- 修复首页 Material 卡片网格的 emoji 图标渲染

---

## v0.2.0 — 2026-04

**主题：** 视觉风格与国际化。

### 新增
- 尼尔：机械纪元自定义主题（`nier.css`）— 暖奶油色浅色模式、深炭色深色模式
- 完整的 i18n 支持，使用 `mkdocs-static-i18n` — 英文（默认）和中文
- 所有用户文档页面的中文翻译
- 明暗模式切换，配合尼尔风格调色板
- HUD 风格几何装饰、定制字体（JetBrains Mono、Noto Sans/SC）
- MkDocs Material 主题：导航标签页、搜索、代码复制

### 变更
- 文档站点通过 `deploy-pages.yml` 部署至 GitHub Pages
- 版本宏系统（`{{ nines_version }}`）实现版本自动追踪

---

## v0.1.0 — 2026-03

**主题：** MVP — 三顶点架构完整实现。

### 新增
- **V1 评估与基准测试**
    - 基于 TOML 的任务定义，包含结构化输入/期望模式
    - 多种评分器类型：精确匹配、模糊匹配、量规、复合评分
    - `EvalRunner` 可配置执行管线
    - N 轴矩阵评估
    - 统计可靠性指标：pass@k、Pass^k、Pass³
    - 三层沙箱隔离执行（进程 + 虚拟环境 + 临时目录）
    - 4 维污染检测（环境变量、文件、目录、sys.path）
    - Markdown 和 JSON 报告生成
- **V2 信息采集**
    - GitHub REST 和 GraphQL 数据源采集器
    - arXiv 搜索和元数据采集器
    - SQLite 存储与 FTS5 全文搜索
    - 令牌桶速率限制（按数据源）
    - 基于快照的增量采集与变更检测
- **V3 代码分析**
    - 基于 AST 的代码解析和元素提取
    - 圈复杂度计算
    - 跨文件依赖图构建
    - 多策略分解（功能、关注点、层次）
    - 知识单元索引与搜索
    - 架构模式识别
- **自迭代（MAPIM）**
    - 4 个类别共 19 个自评估维度
    - 差距检测与严重性分级
    - 改进规划，每次迭代最多 3 个行动
    - 4 方法收敛检测（滑动方差、相对改进、Mann-Kendall、CUSUM）
    - 可配置权重的复合评分
- **智能体技能支持**
    - `nines install` 命令，支持 Cursor 和 Claude Code 集成
    - 双平台技能模板
- **CLI 命令行**
    - `nines eval` — 对 TOML 任务文件运行评估
    - `nines collect` — 从 GitHub 和 arXiv 采集数据
    - `nines analyze` — 分析代码库
    - `nines self-eval` — 运行自评估
    - `nines iterate` — 运行 MAPIM 自我改进循环
- **文档**
    - MkDocs 站点：用户指南、架构文档、API 参考
    - 快速入门指南及分步示例
    - 全面的设计理念页面
    - 19 维评估标准参考
    - 开发计划和路线图
    - 贡献指南与模块责任矩阵
- **基础设施**
    - Python 3.12+ 配合 `uv` 包管理
    - GitHub Actions：版本同步检查、文档部署
    - 主种子传播的确定性执行
    - 基于协议的可扩展性（PEP 544）
    - `structlog` 结构化日志
    - 渐进式配置深度（CLI → 项目 → 用户 → 默认值）
