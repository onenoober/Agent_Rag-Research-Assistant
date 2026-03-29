# 检索链路优化模块

本文档详细说明科研助手 agent 二期新增的检索链路优化模块，包括 query rewrite 流程、keyword retrieval 流程、hybrid retrieval 合并逻辑、rerank 开关说明、search pipeline 调用方式以及 rag adapter 增强检索使用方式。

## 1. 整体架构

检索链路优化采用「扩展现有」而非「新增文件」策略：

- 不新增 `rag_adapter_v2.py`
- 在现有 `src/agent/adapters/rag_adapter.py` 上扩展
- 新增配置开关控制启用

```
用户查询 → Query Rewriter → Hybrid Search → Reranker → 最终结果
                              ↓
                         Debug Trace
```

## 2. Query Rewrite 流程

### 2.1 概述

Query Rewrite 位于 `src/agent/retrieval/query_rewriter.py`，复用现有 `QueryProcessor`，扩展 Agent 层适配。

### 2.2 实现原理

```python
from src.agent.retrieval.query_rewriter import QueryRewriter

rewriter = QueryRewriter()

# 重写查询
result = rewriter.rewrite("什么是机器学习")

print(result.original_query)      # "什么是机器学习"
print(result.rewritten_queries)   # ["什���是机器学习"]
print(result.keywords)            # ["机器学习"]
```

### 2.3 核心逻辑

1. **原始 query 清洗**：去除停用词、特殊字符
2. **关键词提取**：调用 `QueryProcessor` 提取关键词
3. **多查询改写接口**：预留扩展接口，默认返回原查询

```python
# 内部实现
def rewrite(self, query: str) -> RewriteResult:
    # 直接复用 QueryProcessor
    processed = self._processor.process(query)
    
    return RewriteResult(
        original_query=query,
        rewritten_queries=[query],  # 可扩展多查询
        keywords=processed.keywords or [],
        filters=processed.filters or {},
    )
```

### 2.4 配置开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| enable_query_rewrite | bool | False | 是否启用查询重写 |

在 `config/settings.yaml` 中配置：

```yaml
retrieval:
  enable_query_rewrite: false  # 本地部署默认关闭
```

## 3. Keyword Retrieval 流程

### 3.1 复用现有 SparseRetriever

Keyword Retrieval 复用现有 `src/core/query_engine/sparse_retriever.py`，不重新开发。

### 3.2 实现方式

在 `SearchPipeline` 中直接注入使用：

```python
from src.core.query_engine import create_sparse_retriever

class SearchPipeline:
    def __init__(self, settings):
        # 复用现有 SparseRetriever
        self._sparse_retriever = create_sparse_retriever(settings)
```

### 3.3 BM25 检索

SparseRetriever 使用 BM25 算法进行关键词检索：

- 计算查询词在文档中的出现频率
- 使用 IDF 加权
- 按相关性得分排序

## 4. Hybrid Retrieval 合并逻辑

### 4.1 复用现有 HybridSearch

Hybrid Retrieval 复用现有 `src/core/query_engine/hybrid_search.py`，通过 `create_hybrid_search()` 创建实例。

### 4.2 合并算法

采用 RRF（Reciprocal Rank Fusion）排名融合：

```python
# RRF 公式
score = sum(1.0 / (k + rank)) for each retriever
```

其中 k=60（默认常数）。

### 4.3 合并约束

合并逻辑必须满足：

1. **向量召回结果不丢失**：Dense Retriever 结果全部参与合并
2. **关键词召回结果不丢失**：Sparse Retriever 结果全部参与合并
3. **相同 chunk 结果去重**：相同 chunk_id 只保留排名最高的
4. **合并后统一排序**：按 RRF 得分排序
5. **metadata 保持一致**：保留各路召回的 metadata

### 4.4 配置开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| enable_hybrid | bool | True | 是否启用混合检索 |

在 `config/settings.yaml` 中配置：

```yaml
retrieval:
  enable_hybrid: true
  dense_top_k: 10
  sparse_top_k: 10
  fusion_top_k: 20
```

## 5. Rerank 开关说明

### 5.1 复用现有 Reranker

Rerank 复用现有 `src/libs/reranker/`，通过 `RerankerFactory.create()` 创建实例。

### 5.2 支持的类型

- **Cross-Encoder Reranker**：使用 cross-encoder 模型重排
- **LLM Reranker**：使用 LLM 进行重排

### 5.3 配置开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| rerank.enabled | bool | False | 是否启用 rerank |
| rerank.provider | str | "local" | rerank provider |
| rerank.model | str | - | rerank 模型 |

在 `config/settings.yaml` 中配置：

```yaml
rerank:
  enabled: false
  provider: "local"
  model: "cross-encoder"
```

### 5.4 关闭 rerank 时的行为

关闭 rerank 时，pipeline 仍然有效，直接输出 hybrid search 的结果：

```python
# rerank 关闭时
if not self._reranker.is_enabled:
    final_result = hybrid_result.results  # 直接返回
else:
    final_result = self._reranker.rerank(...)  # 重排后返回
```

## 6. Search Pipeline 调用方式

### 6.1 基本用法

```python
from src.agent.retrieval.search_pipeline import SearchPipeline, RetrievalConfig

# 创建检索管道（使用默认配置）
pipeline = SearchPipeline()

# 执行检索
results = pipeline.search("什么是深度学习", top_k=10)
```

### 6.2 配置用法

```python
# 使用自定义配置
config = RetrievalConfig(
    enable_rewrite=True,
    enable_hybrid=True,
    enable_rerank=True,
    dense_top_k=10,
    sparse_top_k=10,
    fusion_top_k=20
)

pipeline = SearchPipeline(config=config)
results = pipeline.search("什么是深度学习", top_k=10)
```

### 6.3 返回结果结构

```python
from src.agent.schemas.retrieval import RetrievalResult

result = pipeline.search("什么是深度学习")

# 检索结果列表
print(result.results)  # List[RetrievalCandidate]

# Debug trace
print(result.debug_trace)
# {
#     "rewritten_queries": ["什么是深度学习"],
#     "dense_hits": 8,
#     "sparse_hits": 12,
#     "merged_hits": 18,
#     "reranked_hits": 10  # 仅在 rerank 开启时
# }
```

### 6.4 Debug Trace 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| rewritten_queries | List[str] | 重写后的查询列表 |
| dense_hits | int | 向量检索命中数 |
| sparse_hits | int | 关键词检索命中数 |
| merged_hits | int | 混合检索合并后总数 |
| reranked_hits | int | rerank 后的数量（仅在 rerank 开启时） |

## 7. RAG Adapter 增强检索使用方式

### 7.1 扩展现有 RAGAdapter

增强检索不是新增文件，而是在现有 `src/agent/adapters/rag_adapter.py` 上扩展。

### 7.2 新增配置开关

在 `rag_adapter.py` 中新增以下配置项：

```python
class RAGAdapter:
    def __init__(self, settings):
        # 原有配置保持不变
        self._top_k = settings.rag.top_k
        
        # 新增配置开关（带默认值）
        self._enable_query_rewrite = getattr(
            settings, 'retrieval', {}
        ).get('enable_query_rewrite', False)
        self._enable_hybrid = getattr(
            settings, 'retrieval', {}
        ).get('enable_hybrid', True)
        self._enable_rerank = getattr(
            settings, 'rerank', {}
        ).get('enabled', False)
```

### 7.3 新增方法 search_enhanced()

```python
# 使用增强检索（需要配置开关开启）
results = rag_adapter.search_enhanced(
    query="什么是机器学习",
    top_k=10
)
```

### 7.4 原有方法行为不变

**重要**：原有 `search()` 方法的行为保持不变，确保向后兼容。

```python
# 原有方法（行为不变）
results = rag_adapter.search("什么是机器学习")

# 增强方法（需要开启配置）
results = rag_adapter.search_enhanced("什么是机器学习")
```

### 7.5 配置示例

在 `config/settings.yaml` 中配置增强检索：

```yaml
rag:
  top_k: 5

retrieval:
  enable_query_rewrite: false
  enable_hybrid: true
  dense_top_k: 10
  sparse_top_k: 10
  fusion_top_k: 20

rerank:
  enabled: false
  provider: "local"
  model: "cross-encoder"
```

### 7.6 新旧链路切换方式

| 场景 | 调用方法 | 说明 |
|------|----------|------|
| 使用原有检索 | `rag_adapter.search()` | 行为不变 |
| 使用增强检索 | `rag_adapter.search_enhanced()` | 需要配置开启 |

## 8. 快速验证命令

```bash
# 验证模块导入
python -c "from src.agent.retrieval.search_pipeline import SearchPipeline; print('OK')"
python -c "from src.agent.adapters.rag_adapter import RAGAdapter; print('OK')"

# 运行 Phase 9 单元测试
python -m pytest tests/unit/test_query_rewriter.py tests/unit/test_search_pipeline.py -v

# 运行 Phase 9 集成测试
python -m pytest tests/integration/test_rag_adapter_enhanced_integration.py -v
```

## 9. 检索链路汇总

```
┌─────────────────────────────────────────────────────────────────┐
│                        SearchPipeline                          │
├─────────────────────────────────────────────────────────────────┤
│  Query (原始查询)                                               │
│       ↓                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  QueryRewriter (可选)                                    │  │
│  │  - 关键词提取                                            │  │
│  │  - 查询清洗                                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│       ↓                                                         │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ DenseRetriever  │    │ SparseRetriever │                    │
│  │ (向量检索)       │    │ (关键词检索)     │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           ↓                        ↓                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  HybridSearch (RRF 合并)                                  │  │
│  │  - 去重                                                    │  │
│  │  - 排序                                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│       ↓                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Reranker (可选)                                          │  │
│  │  - Cross-Encoder                                          │  │
│  │  - LLM Rerank                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│       ↓                                                         │
│  Final Results (最终结果)                                       │
│       ↓                                                         │
│  Debug Trace (调试信息)                                        │
└─────────────────────────────────────────────────────────────────┘
```