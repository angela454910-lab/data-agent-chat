# Agent 对话数据分析项目方案

## 1. 项目目标

建设一个面向业务用户的数据问答 Agent。用户用自然语言提问，系统自动识别需要查询的数据表和字段，执行安全的数据查询与轻量分析，并以对话形式返回结论、关键指标、证据数据和可继续追问的问题。

## 2. 典型用户流程

1. 用户输入问题，例如“最近 30 天销售额是多少，哪个渠道贡献最大？”
2. Agent 理解意图：指标是销售额，维度是渠道，时间范围是最近 30 天。
3. Agent 匹配数据表：`orders`、`channels`。
4. Agent 生成分析计划：过滤时间、聚合收入、按渠道排序、总结贡献。
5. API 执行查询和分析。
6. UI 展示回答、命中表、分析步骤、指标卡片和明细数据。

## 3. 总体架构

```text
Browser UI
  |
  | POST /api/chat
  v
API Server
  |
  +-- Conversation Controller
  +-- Agent Orchestrator
      |
      +-- Intent Parser
      +-- Table Router
      +-- Query Planner
      +-- Analysis Engine
      +-- Answer Composer
  |
  +-- Data Adapter
      |
      +-- Sample Data / SQL DB / Data Warehouse
```

## 4. 后端模块设计

### 4.1 Conversation Controller

负责接收用户消息、维护会话上下文、调用 Agent、返回结构化结果。生产版本应为每个会话分配 `conversation_id`，并将其传入 Agent 运行配置中的 `thread_id`。当前核心接口：

- `POST /api/chat`
- `GET /api/schema`
- `GET /api/health`

生产版本的多轮对话不应仅依赖模型阅读完整消息历史，而应维护持久化的结构化 `AnalysisContext`。其保存当前活跃分析的指标、维度、时间范围、筛选条件、指标口径版本、最近查询计划、结果摘要与待澄清项。用户提出“按华东拆分一下”“改成上季度”“第一名为什么高”等追问时，系统先加载该 Context，再将用户输入解析为受约束的增量修改（patch），校验后重新执行查询。

`AnalysisContext` 的存储范围为一个 `conversation_id`，可使用数据库持久化，并以 Redis 缓存热会话状态；页面刷新、断线重连或跨设备访问同一会话时均可恢复。新建对话或从历史轮次创建分支时，应创建新的 Context，避免不同分析主题相互污染。

为避免长对话导致上下文膨胀，每轮模型调用按以下分层组装上下文：

- 必带：当前 `AnalysisContext`（小型、结构化）与用户/租户权限。
- 按需带入：最近 3-6 轮自然语言消息，用于保留指代和表达方式。
- 检索带入：与当前问题相关的历史查询计划、结果摘要或明细快照，而非全量历史。

DeepAgents/LangGraph 的 checkpoint 用于保存图执行状态和消息状态；业务侧仍需单独维护 `AnalysisContext`，以确保指标、筛选和查询计划可验证、可审计、可复现。

### 4.2 Schema Catalog

维护数据表、字段、业务含义、字段别名、常见指标、表关系。它是 Agent 正确选择数据表的基础。

生产环境建议将 schema catalog 存在数据库或配置中心，并提供后台页面维护字段描述和业务口径。

### 4.3 Table Router

根据用户问题匹配候选表，综合：

- 表名、字段名、字段描述
- 业务关键词和同义词
- 指标词，例如销售额、订单数、退款率、转化率
- 上下文中的历史追问

当前实现为规则匹配，后续可升级为 embedding 检索 + LLM rerank。

### 4.4 Query Planner

将自然语言问题转成结构化查询计划：

```json
{
  "tables": ["orders", "channels"],
  "timeRange": "last_30_days",
  "metrics": ["revenue"],
  "dimensions": ["channel"],
  "analysisType": "ranking"
}
```

生产环境建议让 LLM 只输出 JSON plan，再由后端校验和执行，不允许模型直接拼接任意 SQL。

### 4.5 Analysis Engine

执行聚合、排序、趋势、占比、异常点识别等轻量分析。复杂分析可以扩展到 Python worker、Spark、Flink 或 BI 语义层。

### 4.6 Answer Composer

将分析结果转成自然语言回答，并附带证据数据、使用表和建议追问。若接入 LLM，可以把结构化结果交给模型润色，但事实数据必须来自查询结果。

### 4.7 Context Resolver 与分析状态更新

`Context Resolver` 位于 Conversation Controller 与 Agent Orchestrator 之间，负责加载和选择本轮需要的上下文；它不是将会话原文无差别地拼接进 prompt。职责包括：

- 从 `conversation_id` 加载当前 `AnalysisContext`、最近消息和候选历史快照。
- 对明确的系统操作（新建对话、清空条件、撤销、重试）采用确定性规则处理。
- 让 LLM 在 JSON Schema 约束下输出 `modify_active_analysis`、`start_new_analysis`、`reference_history` 或 `request_clarification` 等动作及 patch。
- 使用代码校验 patch 中的指标、字段、枚举值、权限和预算，并将合法的更新持久化。
- 当用户问题存在口径歧义、缺少时间范围或会导致高成本查询时，返回澄清问题或待确认的查询计划，而不是直接执行。

例如，当前 Context 为“最近 30 天、按渠道统计净销售额”，用户输入“按华东拆分一下”时，模型只需输出对 `filters.region` 的增量修改；时间范围、指标和维度由代码继承并校验。

## 5. 前端 UI 设计

第一屏就是可用的 Agent 工作台，而不是介绍页。核心区域：

- 左侧：schema 浏览和示例问题
- 中间：对话消息流
- 右侧：当前回答的分析计划、命中表、指标结果、明细表格
- 底部：输入框和发送按钮

交互要求：

- 支持 Enter 发送、Shift+Enter 换行
- 发送中显示加载状态
- 错误提示可读
- 表和字段命中可解释
- 回答中的结果和证据数据同步展示

### 5.1 生产级分析交互闭环

除基础问答外，生产版本应让业务用户完成“提出问题、确认口径、分析、验证、追问、沉淀与交付”的完整闭环。优先支持以下功能：

1. **多轮连续分析**：基于 `AnalysisContext` 继承上轮指标、时间范围、维度和筛选条件；支持修改条件、引用上轮排名/明细、撤销与从历史轮次分支出新分析。
2. **歧义澄清与执行确认**：当指标口径、时间范围或分析对象不明确时，先以可选项向用户澄清；对高成本、范围较大或导出类分析，先展示查询计划与影响范围，确认后执行。
3. **结果可解释与可验证**：每个答案展示指标口径、公式、时间范围、筛选条件、数据更新时间、命中数据集和证据数据；用户可展开查询计划或查看明细。
4. **图表、下钻与对比**：按结果类型自动推荐趋势、排行、漏斗、分布等图表；支持点击维度继续下钻、固定两个对象进行对比，以及在图表上直接修改筛选条件。
5. **分析产物沉淀**：支持保存会话、收藏问题、分享结果、导出表格/报告、创建定时订阅；常用分析可保存为可复用模板。
6. **用户反馈与纠错**：支持对回答标记有用/无用、反馈指标或结论错误、提交推荐问法；后台将反馈聚合为待优化的指标、知识和评测用例。

### 5.2 业务知识与分析能力扩展

业务知识不应仅以自由问答形式存在。用户应能查看答案引用的知识来源、生效版本和关联指标，并在知识未覆盖时得到明确提示。知识运营侧应支持内容上传、版本/生效时间、审核和失效管理。

数据分析能力从简单查询逐步扩展为面向业务的分析动作：

- 基础：聚合、排行、趋势、占比、条件筛选与跨维度拆分。
- 进阶：同比/环比、漏斗、留存、分群、Top N、异常点识别与归因线索。
- 交付：自动生成可编辑的分析摘要、日报/周报和面向不同角色的结论版本。

## 6. 数据安全和权限

生产版本必须实现：

- 用户身份认证和租户隔离
- 表级、列级、行级权限控制
- 敏感字段脱敏
- SQL 白名单和查询 AST 校验
- 查询超时和结果行数限制
- 审计日志：用户、问题、表、字段、SQL、耗时、返回行数
- Prompt injection 防护：模型不能越权选择表或绕过权限

## 7. 技术选型建议

### MVP

- Frontend：React 或静态 HTML/JS
- Backend：Node.js / Python FastAPI
- Agent：规则路由 + LLM JSON plan
- DB：PostgreSQL / MySQL / SQLite

### 生产增强

- 语义层：Cube、dbt metrics、MetricFlow 或自研指标口径层
- 检索：向量库保存表字段说明和业务知识
- 工作流：LangGraph、OpenAI Responses API tool-calling 或自研 orchestrator
- 异步任务：BullMQ、Temporal、Celery
- 观测：OpenTelemetry、Prometheus、结构化日志

## 8. 里程碑

### Phase 1: MVP

- 完成 Agent UI
- 完成 schema catalog
- 完成表识别和查询计划
- 支持 5-10 个核心业务问题
- 返回可解释答案和证据数据

### Phase 2: 接真实数据

- 接入数据库适配器
- 加入权限、审计、查询超时
- 增加指标口径配置
- 支持会话上下文追问
- 接入 `conversation_id`、Agent checkpoint 与持久化 `AnalysisContext`
- 支持基于 Context patch 的条件继承、历史结果引用与多轮澄清
- 展示指标口径、时间范围、筛选条件、数据更新时间与证据数据
- 支持结果图表、维度下钻、条件修改与基础同比/环比
- 支持保存会话、收藏问题与导出分析结果

### Phase 3: 智能增强

- schema embedding 检索
- LLM JSON plan 生成
- 多轮澄清
- 异常检测、同比环比、归因分析
- 可导出分析报告
- 支持会话分享、定时订阅、可复用分析模板与报告自动生成
- 支持知识来源引用、知识版本管理与知识缺口提示
- 支持回答反馈、结论纠错和高频问题/失败问题的运营看板
