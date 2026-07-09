# Data Agent Chat - Backend

基于 LangChain + LangGraph 的数据问答 Agent 后端服务。同时负责构建后的 React 前端静态文件服务。

## 架构

```
用户 → FastAPI (3009) → Supervisor Agent → 路由选择
                         │                  ├─→ Data Analysis Agent (数据查询)
                         │                  └─→ Business Knowledge Agent (业务知识)
                         └─→ 静态文件服务 (web/dist)
```

- **FastAPI**: HTTP 服务，提供 REST + SSE 流式接口 + 前端静态文件
- **LangGraph**: Multi-Agent 编排（Supervisor 模式）
- **LangChain + OpenAI 兼容接口**: LLM 调用（通过 API Gateway）
- **Mock 数据**: pandas DataFrame 模拟数据库

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 构建前端

```bash
cd web
npm install
npm run build
```

### 3. 配置环境变量

编辑 `.env` 文件：

```env
# OpenAI 兼容 API 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://your-api-gateway/v1
MODEL_NAME=your-model-name

# true = Mock 模式（不调用 LLM，使用规则匹配，适合开发测试）
# false = 真实 API 模式（调用 LLM，需要有效 API Key 和网络）
USE_MOCK=false
```

### 4. 启动服务

```bash
# 方式一：使用启动脚本（自动构建前端 + 启动后端）
./start.sh

# 方式二：手动启动
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3009 --reload
```

### 5. 访问

- **Agent Chat UI**: http://127.0.0.1:3009
- **API 文档**: http://127.0.0.1:3009/docs
- **健康检查**: http://127.0.0.1:3009/api/health

## 开发模式

前端开发时可以使用 Vite 热更新：

```bash
# 终端 1：启动后端
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 3009 --reload

# 终端 2：启动前端开发服务器
cd web
npm run dev
```

前端运行在 `http://127.0.0.1:3008`，API 请求自动代理到后端 3009 端口。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | Agent Chat UI（构建后的 React 应用） |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/schema` | 获取数据表 Schema |
| `POST` | `/api/chat` | 对话（JSON） |
| `POST` | `/api/chat/stream` | 对话（SSE 流式） |

## 示例问题

### 数据分析
- "最近 30 天销售额是多少，哪个渠道贡献最大？"
- "各地区订单量排名如何？"
- "退款率怎么样？"
- "新用户转化率如何？"

### 业务知识
- "退款政策是什么？"
- "ROI 怎么计算？"
- "企业版和专业版有什么区别？"
- "转化率的定义是什么？"

## 运行模式

### Mock 模式（`USE_MOCK=true`）

不调用 LLM，使用关键词匹配生成预设响应。无需 API Key 和网络。适合：
- 前端 UI 开发
- Agent 路由逻辑测试
- 离线开发环境

### 真实 API 模式（`USE_MOCK=false`）

通过 OpenAI 兼容接口调用 LLM。需要：
1. 有效的 API Key（`OPENAI_API_KEY`）
2. 可访问的 API Gateway（`OPENAI_BASE_URL`）
3. 模型已在 Gateway 上开通权限（`MODEL_NAME`）

## 项目结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口（API + 前端静态文件）
│   ├── llm.py               # LLM 配置（OpenAI 兼容接口）
│   ├── agents/
│   │   ├── supervisor.py    # Supervisor 编排（路由）
│   │   ├── data_analysis.py # 数据分析 Agent
│   │   └── business_knowledge.py  # 业务知识 Agent
│   ├── tools/
│   │   ├── query.py         # 查询工具（6 个）
│   │   └── mock_data.py     # Mock 数据（pandas DataFrame）
│   ├── schema/
│   │   └── catalog.py       # Schema 目录
│   └── knowledge/
│       └── loader.py        # 业务知识库加载
├── test.html                # 备用简单测试页面
├── requirements.txt
├── .env                     # 环境变量配置
└── start.sh                 # 启动脚本
```

## 技术栈

- Python 3.10+
- FastAPI + Uvicorn
- LangChain + LangGraph
- pandas
- OpenAI 兼容 API（通过 API Gateway）
