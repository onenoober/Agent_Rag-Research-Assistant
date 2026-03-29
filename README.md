# Modular RAG & Agent System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-ff69b4.svg)](https://github.com/astral-sh/ruff)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green)](https://modelcontextprotocol.io/)

> 一个模块化的 RAG 检索系统与智能 Agent 系统，通过 MCP 协议暴露工具接口，支持 GitHub Copilot / Claude 等 AI 助手直接调用。

---

## 目录

- [Part 1: RAG-MCP Server](#part-1-rag-mcp-server)
- [Part 2: Agent System](#part-2-agent-system)
- [快速开始](#快速开始)
- [常见问题](#常见问题)

---

# Part 1: RAG-MCP Server

> 模块化检索增强生成（RAG）MCP Server

## 项目概述

RAG-MCP Server 是一个**可插拔、可观测**的模块化 RAG 服务框架，将 RAG 系统的核心环节串联为一个完整的、可运行的工程项目：

- **检索**：Hybrid Search + Rerank（混合检索 + 重排序）
- **多模态**：Image Captioning（图像描述生成）
- **评估**：Ragas + Custom（双评估体系）
- **协议**：MCP（Model Context Protocol）

## 核心能力

| 模块 | 能力 | 说明 |
|------|------|------|
| **Ingestion Pipeline** | PDF → Markdown → Chunk → Embedding → Upsert | 全链路数据摄取 |
| **Hybrid Search** | Dense + Sparse + RRF Fusion + Rerank | 两段式检索架构 |
| **MCP Server** | 标准 MCP 协议暴露 Tools | `query_knowledge_hub`、`list_collections` |
| **Dashboard** | Streamlit 六页面管理平台 | 系统总览 / 数据浏览 / 评估面板 |
| **Evaluation** | Ragas + Custom 评估体系 | Golden Test Set 回归测试 |
| **Observability** | 全链路白盒化追踪 | Ingestion 与 Query 中间状态透明 |

## 技术亮点

**🔌 全链路可插拔架构**：LLM / Embedding / Reranker / Splitter / VectorStore / Evaluator 均定义抽象接口，支持"乐高积木式"替换。

**🔍 混合检索 + 重排**：BM25 稀疏检索 + Dense Embedding 语义检索，RRF 融合后可选 Cross-Encoder / LLM Rerank 精排。

**🖼️ 多模态图像处理**：利用 Vision LLM 自动生成图片描述并缝合进 Chunk，实现"搜文字出图"。

**📡 MCP 生态集成**：遵循 Model Context Protocol 标准，可直接对接 GitHub Copilot、Claude Desktop 等 MCP Client。

**🧪 三层测试体系**：Unit / Integration / E2E 分层测试，覆盖独立模块逻辑、模块间交互、完整链路。

## 项目结构

```
MODULAR-RAG-MCP-SERVER/
├── src/
│   ├── core/                  # 核心配置与查询引擎
│   ├── ingestion/             # 数据摄取管道
│   │   ├── document_manager.py
│   │   ├── pipeline.py
│   │   ├── embedding/         # 嵌入层
│   │   ├── storage/          # 存储层
│   │   └── transform/        # 转换层
│   ├── libs/                  # 可插拔组件库
│   │   ├── llm/             # LLM 工厂
│   │   ├── embedding/       # Embedding 工厂
│   │   ├── vector_store/    # 向量存储
│   │   ├── reranker/        # 重排序
│   │   └── splitter/        # 分块策略
│   ├── observability/         # 可观测性
│   │   └── dashboard/       # Streamlit Dashboard
│   └── agent/                 # Agent 层 (见 Part 2)
├── config/
│   └── settings.yaml         # 配置文件
├── docs/                      # 文档
├── tests/                     # 测试
└── DEV_SPEC.md               # 开发规格文档
```

> 📖 详细架构设计请参阅 [DEV_SPEC.md](DEV_SPEC.md)

---

# Part 2: Agent System

> 基于 LangGraph 的智能研究助手 (Research Assistant)

## 项目概述

Agent 系统基于 **LangGraph** 框架构建，作为 RAG-MCP Server 的核心上层应用层。负责接收用户查询，通过**规划（Planning）**、**工具执行（Tool Execution）**和**记忆管理（Memory Management）**等机制，结合底层 RAG 检索能力，提供智能问答服务。

## 核心特点

### 1️⃣ LangGraph 工作流架构

Agent 采用 LangGraph 框架构建有向无环图（DAG）工作流：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ load_memory │ ──▶ │   planner   │ ──▶ │  tool_executor  │
│  (记忆加载) │     │   (规划器)   │     │   (工具执行)     │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   finalize  │ ◀── │memory_writer│ ◀── │ answer_builder  │
│   (完成)    │     │  (记忆写入)  │     │   (答案构建)     │
└─────────────┘     └─────────────┘     └─────────────────┘
```

**核心设计要点**：

- **状态驱动**：通过 `AgentState` 数据类在节点间传递上下文
- **条件边**：基于 Planner 决策动态选择下一跳节点
- **Checkpointer**：使用 `MemorySaver` 实现会话状态持久化
- **异步执行**：所有节点均为异步函数，支持高并发

### 2️⃣ 工具系统 (Tool System)

| 工具名称 | 功能描述 |
|---------|---------|
| `rag_search` | 知识库检索 |
| `calculator` | 数学计算 |
| `file_upload` | 文件上传与索引 |

### 3️⃣ 记忆管理系统

| 记忆类型 | 存储位置 | 生命周期 |
|---------|---------|---------|
| **短期记忆** | SQLite `chat_history` 表 | 会话级 |
| **长期记忆** | SQLite `user_preferences` 表 | 持久化 |
| **工作上下文** | `AgentState.memory_context` | 单轮交互 |

### 4️⃣ RAG 深度集成

- **标准检索**：Hybrid Search 混合检索
- **增强检索**：Query Rewrite、Cross-Encoder Rerank
- **公式增强**：数学公式检测与跨引用检索
- **引用透明**：每个答案附带来源引用

## 技术栈

| 组件 | 选型 |
|-----|------|
| **Agent 框架** | LangGraph |
| **LLM 集成** | LangChain LCEL |
| **Web 框架** | FastAPI |
| **UI 框架** | Streamlit |
| **数据库** | SQLite |

## Agent 项目结构

```
src/agent/
├── api/                      # API 层
│   ├── app.py              # FastAPI 应用入口
│   ├── routes_chat.py      # 聊天接口
│   └── routes_health.py    # 健康检查
├── graph/                   # LangGraph 核心
│   ├── builder.py          # 图构建器
│   ├── state.py            # AgentState 定义
│   ├── nodes.py            # 节点实现
│   ├── edges.py            # 边定义
│   └── prompts.py          # LLM Prompt 模板
├── tools/                   # 工具系统
│   ├── base.py             # BaseTool 抽象基类
│   ├── registry.py         # 工具注册表
│   ├── rag_tool.py         # RAG 检索工具
│   ├── calculator_tool.py  # 计算器工具
│   └── file_upload.py      # 文件上传工具
├── memory/                  # 记忆管理
│   ├── manager.py          # 记忆管理器
│   ├── short_term.py       # 短期记忆
│   └── long_term.py        # 长期记忆
├── adapters/                # 适配器层
│   ├── rag_adapter.py      # RAG 适配器
│   ├── citation_adapter.py  # 引用适配器
│   └── ingestion_adapter.py # 摄取适配器
├── services/                # 服务层
│   ├── chat_service.py     # 聊天服务
│   └── stream_service.py   # 流式服务
├── parsers/                # 文档解析器
│   ├── pdf_parser.py       # PDF 解析
│   ├── text_parser.py      # 文本解析
│   └── chunk_builder.py    # 分块构建
├── eval/                    # 评估模块
│   ├── runner.py           # 评估运行器
│   ├── retrieval_eval.py   # 检索评估
│   └── answer_eval.py      # 回答评估
└── apps/
    └── research_agent/      # Streamlit 应用
        ├── pages/
        │   ├── chat.py     # 聊天页面
        │   ├── eval.py     # 评估页面
        │   └── settings.py # 设置页面
        └── components/
            ├── chat_panel.py    # 聊天面板
            ├── uploader.py      # 文件上传
            └── tool_steps.py    # 工具步骤展示
```

> 📖 详细架构设计请参阅 [Agent_DEV_SPEC.md](Agent_DEV_SPEC.md)

## 系统集成关系

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Application (src/agent/)             │
├─────────────────────────────────────────────────────────────┤
│  本项目提供：                                                 │
│  • LangGraph 工作流                                          │
│  • 工具系统 (RAG Search / Calculator / File Upload)          │
│  • 记忆管理 (短期 / 长期)                                     │
│  • API / UI 层                                              │
├─────────────────────────────────────────────────────────────┤
│  依赖 RAG-MCP 项目 (src/):                                   │
│  • 检索能力 (Hybrid Search)                                  │
│  • 摄取能力 (Ingestion Pipeline)                             │
│  • LLM 工厂 / Embedding 工厂                                 │
│  • 向量存储 (Chroma Store)                                   │
│  • Vision LLM (图像描述生成)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

# 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/onenoober/Agent_Rag-Research-Assistant.git
cd Agent_Rag-Research-Assistant
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 配置

编辑 `config/settings.yaml`，配置你的 LLM 和 Embedding Provider：

```yaml
llm:
  provider: "qwen"  # 或 "openai", "ollama", "deepseek"
  model: "qwen-plus"
  api_key: "your-api-key"

embedding:
  provider: "qwen"
  model: "text-embedding-v3"
```

### 4. 启动服务

```bash
# 启动 RAG MCP Server
mcp-server

# 或启动 Agent API
cd src/agent
uvicorn src.agent.api.app:app --reload

# 或启动 Streamlit Dashboard
streamlit run src/observability/dashboard/app.py
```

---

# 常见问题

### 1. 如何切换 Provider（Qwen / DeepSeek / Ollama）？

项目使用**工厂模式（Factory Pattern）**，切换非常方便：

1. 编辑 `config/settings.yaml` 中的 provider 配置
2. 或让 AI 帮你完成：*"帮我切换到 DeepSeek"*

### 2. 支持哪些文档格式？

目前支持：

- PDF (含图片和公式)
- Markdown
- Text
- Word (DOCX)
- Excel (XLSX)

### 3. 如何集成到 AI 工具中（Copilot / Claude Desktop）？

项目是 **MCP Server**，可以集成到任何支持 MCP 协议的 AI 工具：

- **GitHub Copilot**：编写 MCP 配置文件
- **Claude Desktop**：添加 MCP Server 配置
- **Cursor**：直接导入项目

### 4. 遇到问题怎么办？

把错误信息直接丢给 AI，绝大多数问题都能帮你修复。

---

## 📚 文档资源

- 📖 [DEV_SPEC.md](DEV_SPEC.md) — RAG-MCP 开发规格文档
- 📖 [Agent_DEV_SPEC.md](Agent_DEV_SPEC.md) — Agent 开发规格文档
- 📁 [docs/](docs/) — 详细技术文档

> 👉 **项目主页**: https://github.com/onenoober/Agent_Rag-Research-Assistant
