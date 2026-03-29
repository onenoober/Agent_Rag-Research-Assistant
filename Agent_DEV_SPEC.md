# Agent 开发规范 (Agent_DEV_SPEC)

> 版本：0.2 — 基于 MODULAR-RAG-MCP-SERVER 的 Agent 实现规范
>
> 更新时间：2026-03-16

## 目录

- 项目概述
- 核心特点
- 技术选型
- 系统架构与模块设计
- 评估体系
- 可扩展性与未来展望
- 附录

---

## 1. 项目概述

本项目基于 LangGraph 框架构建智能 Agent（智能体），作为 MODULAR-RAG-MCP-SERVER 的核心上层应用层。Agent 负责接收用户查询，通过规划（Planning）、工具执行（Tool Execution）和记忆管理（Memory Management）等机制，结合底层 RAG 检索能力，提供智能问答服务。

### 设计理念 (Design Philosophy)

> **核心定位：基于 RAG 的智能研究助手 (Research Assistant with RAG)**
>
> 本 Agent 项目是 RAG-MCP 项目的上层应用延伸，利用底层强大的检索增强能力，结合 LLM 的推理能力，实现智能化的知识问答与研究辅助。

本项目不仅是一个功能完备的智能问答 Agent，更是一个专为 **AI Agent 技术学习与工程实践** 设计的实战平台：

#### 1️⃣ LangGraph 驱动的工作流 (Learn by Building)

项目架构本身就是 Agent 面试题的"活体答案"。我们将经典 Agent 考点直接融入代码设计，通过动手实践来巩固理论知识：

- LangGraph 状态机与节点设计
- ReAct 模式的工程实现
- 工具调用（Tool Calling）机制
- 短期记忆与长期记忆管理
- 多轮对话上下文管理

#### 2️⃣ 深度集成 RAG 能力 (RAG-Native)

- **RAG 工具化**：RAG 检索能力作为核心工具（`rag_search`）接入 Agent 工具注册表
- **检索增强问答**：结合检索结果与 LLM 生成能力，提供带引用的答案
- **公式增强检索**：支持数学公式的检测与跨引用检索（基于 `formula_enhancer.py`）
- **Query Rewrite**：支持查询重写增强检索效果
- **Rerank 重排序**：支持 Cross-Encoder 重排提升 Top-K 准确率

#### 3️⃣ 完整的技术栈覆盖 (Full-Stack Agent)

- **API 层**：FastAPI 提供的 RESTful 接口
- **Streamlit UI**：基于 Streamlit 的可视化聊天界面
- **评估模块**：完整的检索与回答评估体系

#### 4️⃣ 可观测性与调试能力 (Observability)

- 完整的日志记录与错误追踪
- 工具执行步骤可视化
- 引用来源透明展示

#### 5️⃣ 多模态文档处理能力 (Multimodal Document Processing)

- 支持 PDF、Markdown、TXT、DOCX、Excel 等多种文档格式
- 基于 Vision LLM 的图像描述生成（Image Captioning）
- 数学公式检测与跨引用检索
- 学术论文智能分块

---

## 2. 核心特点

### 2.1 LangGraph 工作流架构

Agent 采用 **LangGraph** 框架构建有向无环图（DAG）工作流，通过状态机模式管理对话生命周期：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ load_memory │ ──▶ │   planner   │ ──▶ │  tool_executor  │
│  (记忆加载)  │     │   (规划器)   │     │   (工具执行)     │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   finalize  │ ◀── │memory_writer│ ◀── │ answer_builder  │
│   (完成)    │     │  (记忆写入)  │     │   (答案构建)     │
└─────────────┘     └─────────────┘     └─────────────────┘
```

**核心设计要点**：

- **状态驱动**：通过 `AgentState` 数据类在节点间传递上下文信息
- **条件边（Conditional Edges）**：基于 Planner 决策动态选择下一跳节点
- **Checkpointer**：使用 `MemorySaver` 实现会话状态持久化
- **异步执行**：所有节点均为异步函数，支持高并发处理

### 2.2 工具系统 (Tool System)

Agent 内置可扩展的工具注册机制：

| 工具名称 | 功能描述 | 核心实现 |
|---------|---------|---------|
| `rag_search` | 知识库检索 | `src/agent/tools/rag_tool.py` |
| `calculator` | 数学计算 | `src/agent/tools/calculator_tool.py` |
| `file_upload` | 文件上传与索引 | `src/agent/tools/file_upload.py` |

**工具架构设计**：

- **BaseTool 抽象基类**：定义工具的统一接口
- **ToolRegistry**：工具注册与管理中心
- **ToolInput/ToolOutput**：标准化的输入输出数据结构

### 2.3 记忆管理系统 (Memory Management)

采用分层记忆架构，平衡响应速度与上下文深度：

| 记忆类型 | 存储位置 | 生命周期 | 用途 |
|---------|---------|---------|------|
| **短期记忆 (Short-Term)** | SQLite `chat_history` 表 | 会话级 | 当前对话历史 |
| **长期记忆 (Long-Term)** | SQLite `user_preferences` 表 | 持久化 | 用户偏好设置 |
| **工作上下文 (Working Context)** | `AgentState.memory_context` | 单轮交互 | 当前轮次上下文 |

**核心实现**：

- `MemoryManager`：统一的记忆管理接口
- `ShortTermMemory`：会话历史管理（已集成到 MemoryManager）
- `LongTermMemory`：用户偏好持久化（通过 user_preferences 表）

### 2.4 检索增强能力 (RAG-Enhanced)

Agent 深度集成底层 RAG 能力：

- **标准检索**：基于 Hybrid Search（稠密+稀疏）的混合检索
- **增强检索**：支持 Query Rewrite、Cross-Encoder Rerank
- **公式增强**：支持数学公式检测与跨引用检索
- **引用透明**：每个答案附带来源引用

---

## 3. 技术选型

### 3.1 核心框架

| 组件 | 选型 | 理由 |
|-----|------|------|
| **Agent 框架** | LangGraph | 状态机工作流、Checkpointer 支持、与 LangChain 无缝集成 |
| **LLM 集成** | LangChain LCEL | 统一的 Runnable 接口、Prompt 模板管理 |
| **Web 框架** | FastAPI | 异步支持、类型安全、自动 API 文档 |
| **UI 框架** | Streamlit | 快速原型开发、交互式数据应用 |
| **数据库** | SQLite | 轻量级、无需部署、本地开发友好 |

### 3.2 Agent 架构技术栈

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Application                        │
├─────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)          │  UI Layer (Streamlit)       │
│  - /api/chat                  │  - Chat Panel                │
│  - /api/chat/stream           │  - Upload Component         │
│  - /health                    │  - Evaluation Page          │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│  - ChatService                │  - StreamService            │
│  - DocumentIngestionService  │  - EvalRunner               │
├─────────────────────────────────────────────────────────────┤
│                   LangGraph Core                             │
│  - AgentGraph (Builder)       │  - AgentState               │
│  - Nodes (planner/executor)  │  - Edges (conditional)      │
├─────────────────────────────────────────────────────────────┤
│                    Tool System                               │
│  - ToolRegistry               │  - BaseTool                 │
│  - RagTool / CalculatorTool  │  - FileUploadTool           │
├─────────────────────────────────────────────────────────────┤
│                   Memory Layer                               │
│  - MemoryManager              │  - SQLite Database          │
│  - ChatHistory               │  - UserPreferences          │
├─────────────────────────────────────────────────────────────┤
│               RAG Adapter (Adapter Pattern)                  │
│  - RAGAdapter                │  - HybridSearch             │
│  - SearchPipeline            │  - FormulaEnhancer          │
├─────────────────────────────────────────────────────────────┤
│              MODULAR-RAG-MCP-SERVER Core                      │
│  - Ingestion Pipeline        │  - Retrieval Pipeline       │
│  - Vector Store (Chroma)     │  - BM25 Indexer             │
│  - Embedding Factory         │  - LLM Factory              │
│  - Vision LLM                │  - Query Engine             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 LLM 集成方案

Agent 通过统一的适配器模式集成多种 LLM，继承自 RAG 项目的 LLM Factory：

**支持的 LLM 提供商**：

- Azure OpenAI
- OpenAI API
- Ollama (本地)
- DeepSeek
- Qwen 系列模型（当前生产环境使用）

### 3.4 Vision LLM 集成

用于图像描述生成和多模态理解：

- **Qwen-VL**：阿里云通义千问视觉模型
- **GPT-4o**：OpenAI 多模态模型
- 支持图像压缩与预处理

---

## 4. 系统架构与模块设计

### 4.1 核心模块结构

```
src/agent/
├── __init__.py                    # 模块初始化
├── api/                           # API 层
│   ├── app.py                     # FastAPI 应用入口
│   ├── deps.py                    # 依赖注入
│   ├── routes_chat.py             # 聊天接口
│   └── routes_health.py           # 健康检查接口
├── graph/                         # LangGraph 核心
│   ├── builder.py                 # 图构建器
│   ├── state.py                   # AgentState 定义
│   ├── nodes.py                   # 节点实现
│   ├── edges.py                   # 边定义
│   └── prompts.py                 # LLM Prompt 模板
├── tools/                         # 工具系统
│   ├── base.py                    # BaseTool 抽象基类
│   ├── registry.py                # 工具注册表
│   ├── rag_tool.py                # RAG 检索工具
│   ├── calculator_tool.py         # 计算器工具
│   └── file_upload.py             # 文件上传工具
├── memory/                        # 记忆管理
│   ├── manager.py                 # 记忆管理器
│   ├── store.py                   # 记忆存储
│   ├── short_term.py              # 短期记忆
│   └── long_term.py               # 长期记忆
├── adapters/                      # 适配器层
│   ├── rag_adapter.py             # RAG 适配器
│   ├── citation_adapter.py        # 引用适配器
│   ├── ingestion_adapter.py       # 摄取适配器
│   └── settings_adapter.py        # 配置适配器
├── services/                      # 服务层
│   ├── chat_service.py            # 聊天服务
│   ├── stream_service.py          # 流式服务
│   └── document_ingestion_service.py  # 文档摄取服务
├── retrieval/                     # 检索层
│   ├── search_pipeline.py         # 搜索管道
│   ├── query_rewriter.py          # 查询重写
│   └── schemas/retrieval.py       # 检索数据模型
├── schemas/                       # 数据模型
│   ├── chat.py                    # 聊天模型
│   ├── citation.py                # 引用模型
│   ├── document.py                # 文档模型
│   └── tool.py                    # 工具模型
├── eval/                          # 评估模块
│   ├── runner.py                  # 评估运行器
│   ├── dataset.py                 # 数据集加载
│   ├── retrieval_eval.py          # 检索评估
│   ├── answer_eval.py             # 回答评估
│   └── reporter.py                # 报告生成
├── parsers/                       # 文档解析器
│   ├── pdf_parser.py              # PDF 解析
│   ├── text_parser.py             # 文本解析
│   ├── chunk_builder.py           # 分块构建
│   ├── document_parser.py         # 文档解析器
│   ├── excel_parser.py            # Excel 解析
│   └── word_parser.py             # Word 解析
├── infra/                         # 基础设施
│   ├── logging.py                 # 日志模块
│   ├── config.py                  # 配置模块
│   └── db.py                      # 数据库模块
└── apps/                          # 应用层
    └── research_agent/            # Streamlit 应用
        ├── app.py                 # 主应用
        ├── pages/                 # 页面
        │   ├── chat.py
        │   ├── eval.py
        │   └── settings.py
        └── components/            # 组件
            ├── uploader.py
            ├── chat_panel.py
            └── tool_steps.py
```

### 4.2 LangGraph 工作流详解

#### 4.2.1 状态定义 (AgentState)

```python
# src/agent/graph/state.py
@dataclass
class AgentState:
    """State that flows through the LangGraph agent."""
    
    query: str                          # 用户查询
    session_id: str                     # 会话 ID
    user_id: Optional[str] = None      # 用户 ID
    top_k: int = 5                     # 检索 Top-K
    temperature: float = 0.7           # LLM 温度
    use_tools: bool = True             # 是否使用工具
    
    messages: List[Dict[str, Any]] = field(default_factory=list)  # 消息历史
    current_message: Optional[Dict[str, Any]] = None              # 当前消息
    
    memory_context: str = ""           # 记忆上下文
    retrieved_docs: List[CitationChunk] = field(default_factory=list)  # 检索文档
    
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)    # 工具调用
    tool_results: List[Dict[str, Any]] = field(default_factory=list) # 工具结果
    
    answer: str = ""                   # 最终答案
    citations: List[CitationChunk] = field(default_factory=list)    # 引用
    
    next_node: Optional[str] = None    # 下一节点
    should_use_tools: bool = False    # 是否使用工具标志
    
    error: Optional[str] = None        # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)          # 元数据
```

#### 4.2.2 节点设计 (Nodes)

| 节点名称 | 功能 | 核心逻辑 |
|---------|------|---------|
| `load_memory` | 加载对话历史 | 从 MemoryManager 获取会话历史，构建 memory_context |
| `planner` | 决策规划 | 分析查询，决定是否使用工具 |
| `tool_executor` | 工具执行 | 遍历 tool_calls，执行并收集结果 |
| `answer_builder` | 答案构建 | 基于检索结果和工具输出生成最终答案 |
| `memory_writer` | 记忆写入 | 将对话内容写入长期记忆 |
| `finalize` | 完成处理 | 添加最终消息到历史，返回结果 |

#### 4.2.3 Planner 决策逻辑

Planner 节点通过 LLM 分析用户查询，输出决策：

```python
# 决策格式
if "USE_TOOLS" in response_content:
    state.should_use_tools = True
    state.next_node = "tool_executor"
    # 解析工具调用
    tool_calls = _parse_tool_calls(response_content)
    state.tool_calls = tool_calls
else:
    state.should_use_tools = False
    state.next_node = "answer_builder"
    state.answer = response_content[:500]
```

#### 4.2.4 条件边 (Conditional Edges)

```python
# src/agent/graph/edges.py
def should_use_tools(state: AgentState) -> str:
    """Determine whether to use tools."""
    return "tool_executor" if state.should_use_tools else "answer_builder"

def should_continue(state: AgentState) -> str:
    """Determine whether to continue to memory writer."""
    return "memory_writer" if state.use_tools else "finalize"
```

### 4.3 工具系统详解

#### 4.3.1 工具基类设计

```python
# src/agent/tools/base.py
@dataclass
class ToolInput:
    """Input schema for tools."""
    query: Optional[str] = None
    top_k: Optional[int] = 5
    file_path: Optional[str] = None
    collection_name: Optional[str] = None
    expression: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ToolOutput:
    """Output schema for tools."""
    success: bool
    result: Any
    error: Optional[str] = None

class BaseTool(ABC):
    """Abstract base class for all agent tools."""
    
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    @abstractmethod
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute the tool with given input."""
        pass
```

#### 4.3.2 RAG 检索工具实现

```python
# src/agent/tools/rag_tool.py
class RagTool(BaseTool):
    """Tool for searching the knowledge base."""
    
    def __init__(self):
        super().__init__(
            name="rag_search",
            description="Search the knowledge base for relevant information",
            input_schema={
                "query": {"type": "string", "required": True},
                "top_k": {"type": "integer", "required": False, "default": 5}
            }
        )
        self._rag_adapter = get_rag_adapter()
    
    async def execute(self, tool_input: ToolInput) -> ToolOutput:
        """Execute the RAG search."""
        query = tool_input.query
        top_k = tool_input.top_k or 5
        
        results = self._rag_adapter.search(query, top_k=top_k)
        
        formatted_results = []
        for idx, result in enumerate(results, 1):
            formatted_results.append({
                "index": idx,
                "chunk_id": result.chunk_id,
                "title": result.title,
                "text": result.text,
                "source": result.source,
                "score": result.score
            })
        
        return ToolOutput(
            success=True,
            result={"results": formatted_results, "count": len(formatted_results)}
        )
```

### 4.4 记忆管理系统详解

#### 4.4.1 记忆管理器

```python
# src/agent/memory/manager.py
class MemoryManager:
    """Manages conversation memory."""
    
    def __init__(self):
        self.max_history = 10
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to session history."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_history (session_id, role, content, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (session_id, role, content)
        )
        conn.commit()
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Message]:
        """Get conversation history for a session."""
        cursor.execute(
            """
            SELECT role, content, created_at
            FROM chat_history
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit)
        )
        rows = cursor.fetchall()
        return [Message(role=r[0], content=r[1], timestamp=r[2]) for r in reversed(rows)]
```

#### 4.4.2 数据库表结构

```sql
-- 聊天历史表
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    citations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_chat_history_session ON chat_history(session_id, created_at);

-- 用户偏好表
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    preferences TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.5 RAG 适配器详解

```python
# src/agent/adapters/rag_adapter.py
class RAGAdapter:
    """Adapter for RAG retrieval operations."""
    
    def __init__(self, collection: Optional[str] = None):
        self._initialized = False
        self._hybrid_search = None
        self._search_pipeline = None
        # 检索配置
        self._enable_query_rewrite = False
        self._enable_hybrid = True
        self._enable_rerank = False
        # 公式增强
        self._formula_enhancer = None
        self._enable_formula_enhancement = False
    
    def search(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """Search knowledge base."""
        if not self._initialized:
            self.initialize()
        
        results = self._hybrid_search.search(query, top_k=top_k)
        
        return [SearchResult(
            chunk_id=r.chunk_id,
            text=r.text,
            score=r.score,
            source=r.metadata.get("source_path", ""),
            title=r.metadata.get("title", ""),
            metadata=r.metadata,
        ) for r in results]
    
    def search_enhanced(
        self,
        query: str,
        top_k: Optional[int] = None,
        enable_query_rewrite: Optional[bool] = None,
        enable_hybrid: Optional[bool] = None,
        enable_rerank: Optional[bool] = None,
    ) -> List[SearchResult]:
        """Search with enhanced pipeline (Query Rewrite, Hybrid, Rerank)."""
        # 使用 SearchPipeline 进行增强检索
        ...
    
    def search_with_formula_enhancement(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[SearchResult]:
        """Search with formula-aware enhancement."""
        # 公式检测与跨引用检索
        ...
```

### 4.6 API 层设计

#### 4.6.1 FastAPI 应用

```python
# src/agent/api/app.py
app = FastAPI(
    title="Research Agent API",
    description="API for the Research Agent",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
```

#### 4.6.2 聊天接口

```python
# src/agent/api/routes_chat.py
class ChatRequest(BaseModel):
    """Chat request model."""
    query: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "default_user"

class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    citations: Optional[dict] = None
    session_id: str

@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)):
    """Handle chat request."""
    response = await chat_service.chat(
        query=request.query,
        session_id=request.session_id,
        user_id=request.user_id
    )
    return ChatResponse(
        answer=response.answer,
        citations=response.citations,
        session_id=response.session_id
    )
```

### 4.7 Streamlit 应用设计

```python
# src/apps/research_agent/app.py
def render_sidebar():
    """Render sidebar with navigation."""
    with st.sidebar:
        st.title("🔬 Research Agent")
        
        page = st.radio(
            "Navigation",
            ["💬 Chat", "📤 Upload", "📊 Evaluation", "⚙️ Settings"]
        )
        
        # Session ID 管理
        session_id = st.text_input("Session ID", value=st.session_state.session_id)
        st.session_state.session_id = session_id
        
        # 清空聊天按钮
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        
        return page
```

---

## 5. 评估体系

### 5.1 评估模块架构

```
src/agent/eval/
├── runner.py              # 评估运行器 (AgentEvalRunner)
├── dataset.py             # 测试数据集加载
├── retrieval_eval.py      # 检索评估 (RetrievalEvaluator)
├── answer_eval.py         # 回答评估 (AnswerEvaluator)
└── reporter.py            # 报告生成 (EvalReporter)
```

### 5.2 检索评估

**评估指标**：

- Hit Rate (@k)：命中率
- MRR (Mean Reciprocal Rank)：平均倒数排名
- NDCG (Normalized Discounted Cumulative Gain)：归一化折损累计增益

### 5.3 回答评估

**评估维度**：

- 关键词覆盖 (Keyword Coverage)
- 参考答案匹配 (Reference Answer Similarity)
- 事实一致性 (Faithfulness)

---

## 6. 可扩展性与未来展望

### 6.1 当前可扩展点

| 扩展方向 | 当前实现 | 扩展方式 |
|---------|---------|---------|
| **新增工具** | BaseTool 子类 | 实现 execute 方法并注册到 ToolRegistry |
| **新 LLM** | LLM Factory | 在 llm_factory.py 添加新 Provider |
| **新检索策略** | RAG Adapter | 实现新的检索方法或 SearchPipeline |
| **新 UI** | Streamlit | 在 apps/research_agent/pages/ 添加新页面 |

### 6.2 计划扩展功能

#### 6.2.1 多 Agent 协作

- 引入 Agent 通信协议
- 支持多 Agent 任务分解
- 实现 Agent 角色分配

#### 6.2.2 高级记忆机制

- 向量化的记忆检索
- 记忆优先级排序
- 记忆遗忘策略

#### 6.2.3 实时学习

- 用户反馈闭环
- 个性化模型微调
- 动态工具推荐

#### 6.2.4 MCP Server 集成

- 将 Agent 封装为 MCP Server
- 支持 MCP Clients 调用
- 标准化工具接口

### 6.3 与 RAG-MCP 项目的关系

本 Agent 项目构建于 **MODULAR-RAG-MCP-SERVER** 之上，利用其核心能力：

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent (src/agent/)                      │
├─────────────────────────────────────────────────────────────┤
│  本项目提供：                                                │
│  • LangGraph 工作流                                         │
│  • 工具系统                                                 │
│  • 记忆管理                                                 │
│  • API/UI 层                                               │
├─────────────────────────────────────────────────────────────┤
│  依赖 RAG-MCP 项目 (src/):                                  │
│  • 检索能力 (RAGAdapter / Hybrid Search)                   │
│  • 摄取能力 (Ingestion Pipeline)                           │
│  • LLM 工厂 (LLM Factory)                                   │
│  • Embedding 工厂 (Embedding Factory)                      │
│  • 向量存储 (Chroma Store)                                  │
│  • 配置管理 (Settings)                                      │
│  • 公式增强 (Formula Enhancer)                             │
│  • Vision LLM (图像描述生成)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 附录

### A. 配置示例

```yaml
# config/settings.yaml (完整配置示例)

# LLM 配置
llm:
  provider: "qwen"
  model: "qwen-plus"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: ""
  temperature: 0.0
  max_tokens: 4096

# Embedding 配置
embedding:
  provider: "qwen"
  model: "text-embedding-v3"
  dimensions: 1024

# Vision LLM 配置
vision_llm:
  enabled: true
  provider: "qwen"
  model: "qwen-omni-turbo"

# 向量存储配置
vector_store:
  provider: "chroma"
  persist_directory: "./data/db/chroma"
  collection_name: "default"

# 检索配置
retrieval:
  dense_top_k: 20
  sparse_top_k: 20
  fusion_top_k: 10
  rrf_k: 60

# Rerank 配置
rerank:
  enabled: true
  provider: "cross_encoder"
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  top_k: 5

# Agent 配置 (扩展配置)
agent:
  session:
    max_history: 10
    default_session_id: "default"
  retrieval:
    default_top_k: 5
    enable_query_rewrite: false
    enable_hybrid: true
    enable_rerank: false
  tools:
    enabled:
      - rag_search
      - calculator
      - file_upload
  max_tool_iterations: 3

# 可观测性配置
observability:
  log_level: "INFO"
  trace_enabled: true
```

### B. API 端点汇总

| 方法 | 路径 | 功能 |
|-----|------|------|
| GET | `/` | 根路径健康检查 |
| GET | `/health` | 健康检查 |
| POST | `/api/chat` | 聊天接口 |
| POST | `/api/chat/stream` | 流式聊天接口 |

### C. 数据库文件

| 文件 | 位置 | 用途 |
|-----|------|------|
| `chat_history.db` | `data/db/` | 对话历史存储 |
| `preferences.db` | `data/db/` | 用户偏好存储 |

### D. 工具详细说明

#### D.1 RAG Search Tool

- **名称**: `rag_search`
- **描述**: 搜索知识库获取相关信息
- **输入参数**:
  - `query` (string, required): 搜索查询
  - `top_k` (integer, optional): 返回结果数量，默认 5

#### D.2 Calculator Tool

- **名称**: `calculator`
- **描述**: 执行数学计算
- **输入参数**:
  - `expression` (string, required): 数学表达式

#### D.3 File Upload Tool

- **名称**: `file_upload`
- **描述**: 上传并索引文件到知识库
- **输入参数**:
  - `file_path` (string, required): 文件路径
  - `collection_name` (string, optional): 集合名称

### E. 环境变量

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API Key | - |
| `OPENAI_API_BASE` | OpenAI API 基础 URL | https://api.openai.com/v1 |

---

> 📝 **文档维护说明**
>
> 本文档基于 `src/agent/` 模块的当前实现编写，反映了项目在 2026-03-16 时的状态。随着项目迭代，本文档将持续更新以保持与代码实现的同步。
>
> 如需更新本文档，请参照 `DEV_SPEC.md` 的格式，确保：
> 1. 技术选型描述与实际代码一致
> 2. 模块设计描述准确反映架构
> 3. 代码示例能够正常运行
