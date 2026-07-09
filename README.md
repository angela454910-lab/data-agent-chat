# Data Agent Chat

对话式数据问答 Agent。用户输入自然语言问题，Supervisor 根据语义路由到对应的子 Agent，查询 Mock 数据或调用 LLM 生成分析结论与业务知识回答。

## 架构

```
用户 → React UI (Vite) → FastAPI (3009) → Supervisor Agent (关键词路由)
                                              ├─→ Data Analysis Agent  → 6 个查询工具 → Mock 数据 (pandas)
                                              └─→ Business Knowledge Agent → 8 篇业务知识文档
```

- **React + TypeScript + Tailwind CSS**: 前端 UI（Vite 构建）
- **FastAPI**: HTTP 服务，提供 REST API 和 SSE 流式接口
- **LangGraph**: Multi-Agent 编排，Supervisor 模式
- **LangChain + OpenAI 兼容接口**: LLM 调用（支持任意 OpenAI 兼容的 API Gateway）
- **pandas DataFrame**: Mock 数据层，模拟真实数据库

## 快速启动

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 安装前端依赖并构建

```bash
cd web
npm install
npm run build
```

### 3. 配置环境变量

编辑 `backend/.env`：

```env
# LLM API 配置（OpenAI 兼容接口）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://your-api-gateway/v1
MODEL_NAME=your-model-name

# true = Mock 模式（不调用 LLM，使用规则匹配响应，适合开发测试）
# false = 真实 API 模式（调用 LLM，需要有效的 API Key 和网络）
USE_MOCK=false
```

### 4. 启动服务

```bash
cd backend
./start.sh
```

或手动启动：

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3009 --reload
```

### 5. 访问

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:3009` | Agent Chat UI（构建后的 React 应用） |
| `http://127.0.0.1:3009/docs` | FastAPI 自动生成的 API 文档 |
| `http://127.0.0.1:3009/api/health` | 健康检查 |

### 开发模式（前端热更新）

如果需要前端开发模式（支持热更新），另开终端：

```bash
cd web
npm run dev
```

前端将运行在 `http://127.0.0.1:3008`，API 请求自动代理到后端 3009 端口。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/schema` | 获取数据表 Schema 列表 |
| `POST` | `/api/chat` | 对话（JSON 请求/响应） |
| `POST` | `/api/chat/stream` | 对话（SSE 流式响应） |

`POST /api/chat` 请求体：

```json
{ "message": "最近30天销售额是多少？" }
```

## 示例问题

**数据分析类**（路由到 Data Analysis Agent）：
- 最近 30 天销售额是多少，哪个渠道贡献最大？
- 各地区订单量排名如何？
- 退款率怎么样？
- 新用户转化率如何？

**业务知识类**（路由到 Business Knowledge Agent）：
- 退款政策是什么？
- ROI 怎么计算？
- 企业版和专业版有什么区别？
- 转化率的定义是什么？

## 运行模式

### Mock 模式（`USE_MOCK=true`）

不调用 LLM，使用关键词匹配生成预设响应。适合无 API 访问时的开发和 UI 测试。

### 真实 API 模式（`USE_MOCK=false`）

通过 OpenAI 兼容接口调用 LLM。需要：
1. 有效的 API Key
2. 网络可访问 API Gateway
3. 模型已在 Gateway 上开通权限

## 目录结构

```text
data-agent-chat/
├── README.md                          # 本文件
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口（服务前端 + API）
│   │   ├── llm.py                     # LLM 配置
│   │   ├── agents/
│   │   │   ├── supervisor.py          # Supervisor 编排（路由）
│   │   │   ├── data_analysis.py       # 数据分析 Agent
│   │   │   └── business_knowledge.py  # 业务知识 Agent
│   │   ├── tools/
│   │   │   ├── query.py               # 查询工具（6 个）
│   │   │   └── mock_data.py           # Mock 数据（pandas）
│   │   ├── schema/
│   │   │   └── catalog.py             # Schema 目录
│   │   └── knowledge/
│   │       └── loader.py              # 业务知识库加载
│   ├── test.html                      # 备用简单测试页面
│   ├── requirements.txt
│   ├── .env                           # 环境变量配置
│   └── start.sh                       # 启动脚本
├── web/                               # React 前端
│   ├── src/
│   │   ├── App.tsx                    # 主布局
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx          # 聊天面板
│   │   │   ├── Sidebar.tsx            # 侧边栏（示例问题 + Schema）
│   │   │   ├── InsightPanel.tsx       # 分析过程面板
│   │   │   └── MessageBubble.tsx      # 消息气泡（支持 Markdown）
│   │   ├── hooks/
│   │   │   └── useChat.ts            # 聊天状态管理
│   │   ├── lib/
│   │   │   └── api.ts                # API 客户端
│   │   └── types.ts                   # TypeScript 类型
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
└── docs/
    └── project-plan.md                # 项目方案文档
```

## 后续扩展

- 替换 Mock 数据层为真实数据库（MySQL / PostgreSQL / ClickHouse / BigQuery）
- 增加更多子 Agent（如报表生成、数据导出）
- 接入向量数据库实现 RAG 业务知识检索
- 增加用户认证、查询权限控制、审计日志
