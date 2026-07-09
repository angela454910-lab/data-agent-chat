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

负责接收用户消息、维护会话上下文、调用 Agent、返回结构化结果。当前核心接口：

- `POST /api/chat`
- `GET /api/schema`
- `GET /api/health`

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

### Phase 3: 智能增强

- schema embedding 检索
- LLM JSON plan 生成
- 多轮澄清
- 异常检测、同比环比、归因分析
- 可导出分析报告
