# 变更日志

NineS 的所有重要变更均记录于此。本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

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
