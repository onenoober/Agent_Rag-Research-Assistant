# 评估模块使用指南

本文档详细说明科研助手 agent 二期新增的评估模块，包括数据集格式、指标定义、runner 运行方式、报告产物说明以及实验结果目录说明。

## 1. 评估模块架构

评估模块采用「复用 + 适配」策略：

- **底层评估引擎**：复用 `src/observability/evaluation/`
- **Agent 适配层**：新建 `src/agent/eval/`
- **评测数据**：新建 `data/eval/`

```
┌─────────────────────────────────────────────────────────────────┐
│                     评估模块架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  smoke集    │    │   dev集     │    │  自定义数据集 │        │
│  │ (5-10条)    │    │ (20-50条)   │    │             │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                   │                   │                │
│         ↓                   ↓                   ↓                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              EvalDatasetLoader (dataset.py)             │   │
│  │              - 评测集加载                                │   │
│  │              - Schema 校验                               │   │
│  │              - 样例过滤                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ↓                                   │
│  ┌─────────��─────┐    ┌───────────────┐    ┌───────────────┐   │
│  │ RetrievalEval │    │  AnswerEval  │    │   (其他评估)  │   │
│  │ (retrieval    │    │   (answer     │    │               │   │
│  │  _eval.py)    │    │   _eval.py)   │    │               │   │
│  └───────────────┘    └───────────────┘    └───────────────┘   │
│                              │                                   │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              EvalRunner (runner.py)                     │   │
│  │              - 批量运行评测                              │   │
│  │              - 配置管理                                  │   │
│  │              - 结果汇总                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Reporter (reporter.py)                      │   │
│  │              - Markdown 报告                             │   │
│  │              - JSON 结果                                 │   │
│  │              - 实验配置                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 数据集格式

### 2.1 文件格式

评测数据集采用 JSONL 格式（每行一个 JSON 对象）：

```json
{"case_id": "case_001", "question": "什么是机器学习？", "expected_keywords": ["机器学习", "人工智能", "模型"], "expected_sources": ["doc1.pdf", "doc2.pdf"]}
{"case_id": "case_002", "question": "深度学习与机器有什么区别？", "expected_keywords": ["深度学习", "神经网络"], "expected_sources": ["doc1.pdf"], "expected_page_no": 3, "expected_section_title": "第一章 概述", "reference_answer": "深度学习是机器学习的一个分支..."}
```

### 2.2 必需字段

每条样例必须包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| case_id | str | 样例唯一标识 |
| question | str | 问题文本 |
| expected_keywords | List[str] | 期望在回答中出现的关键词 |
| expected_sources | List[str] | 期望引用的来源文件 |

### 2.3 可选字段

每条样例可选包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| expected_page_no | int | 期望引用的页码 |
| expected_section_title | str | 期望引用的章节标题 |
| reference_answer | str | 参考答案（用于对比评估） |

### 2.4 非法样例判定

以下情况视为非法样例：

- `case_id` 为空或缺失
- `question` 为空或缺失
- `expected_keywords` 为空列表
- `expected_sources` 为空列表

非法样例在加载时会抛出明确异常：

```python
from src.agent.eval.dataset import EvalDatasetLoader

loader = EvalDatasetLoader()
try:
    dataset = loader.load("data/eval/invalid_cases.jsonl")
except ValueError as e:
    print(f"非法样例: {e}")
```

## 3. Smoke/Dev 数据集区别

### 3.1 Smoke 集

- **位置**：`data/eval/smoke_cases.jsonl`
- **数量**：5-10 条
- **用途**：快速验证功能可用性
- **覆盖**：普通问答、citation 命中、页码返回、章节返回、检索链路基础可用性

```python
# 加载 smoke 集
from src.agent.eval.dataset import load_smoke_dataset

dataset = load_smoke_dataset()
print(f"Smoke 集大小: {len(dataset.cases)}")  # 输出: 5-10
```

### 3.2 Dev 集

- **位置**：`data/eval/dev_cases.jsonl`
- **数量**：20-50 条
- **用途**：开发验证、全面评估
- **覆盖**：多类文档与多类问题形式

```python
# 加载 dev 集
from src.agent.eval.dataset import load_dev_dataset

dataset = load_dev_dataset()
print(f"Dev 集大小: {len(dataset.cases)}")  # 输出: 20-50
```

### 3.3 选择数据集

```python
# 加载特定数据集
loader = EvalDatasetLoader()

# smoke 集
smoke = loader.load("data/eval/smoke_cases.jsonl")

# dev 集
dev = loader.load("data/eval/dev_cases.jsonl")

# 按 case_id 过滤
filtered = loader.load("data/eval/dev_cases.jsonl", case_ids=["case_001", "case_002"])
```

## 4. 指标定义

### 4.1 检索评估指标

RetrievalEval 位于 `src/agent/eval/retrieval_eval.py`

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| Recall@k | 召回率 | 期望来源在 top-k 结果中出现的比例 |
| Hit@k | 命中率 | top-k 结果中包含期望来源的样例比例 |
| MRR | 平均倒数排名 | 第一个期望来源排名的倒数均值 |
| Source Hits | 来源命中数 | 检索结果中包含期望来源的数量 |
| PageNo Hits | 页码命中数 | 检索结果中包含期望页码的数量 |
| SectionTitle Hits | 章节命中数 | 检索结果中包含期望章节标题的数量 |

```python
from src.agent.eval.retrieval_eval import RetrievalEvaluator

evaluator = RetrievalEvaluator()

# 评估检索结果
result = evaluator.evaluate(
    retrieved=[retrieved_chunks],  # 检索返回的结果
    expected_sources=["doc1.pdf", "doc2.pdf"],  # 期望来源
    expected_page_no=3,              # 期望页码
    expected_section_title="第一章 概述",  # 期望章节
    k=10
)

print(f"Recall@10: {result.recall_at_k}")
print(f"Hit@10: {result.hit_at_k}")
print(f"MRR: {result.mrr}")
print(f"PageNo Hits: {result.page_no_hits}")
print(f"SectionTitle Hits: {result.section_title_hits}")
```

### 4.2 回答评估指标

AnswerEval 位于 `src/agent/eval/answer_eval.py`

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| Answer Length | 回答长度 | 回答的字符数 |
| Citation Count | 引用数量 | 回答中引用的 chunk 数量 |
| Keyword Coverage | 关键词覆盖率 | 期望关键词在回答中出现的比例 |
| Completeness | 完整度评分 | 规则式评估，0-100 分 |

```python
from src.agent.eval.answer_eval import AnswerEvaluator

evaluator = AnswerEvaluator()

# 评估回答
result = evaluator.evaluate(
    answer="机器学习是人工智能的一个分支...",
    expected_keywords=["机器学习", "人工智能", "模型"],
    citations=[citation1, citation2]
)

print(f"Answer Length: {result.answer_length}")
print(f"Citation Count: {result.citation_count}")
print(f"Keyword Coverage: {result.keyword_coverage}")
print(f"Completeness: {result.completeness}")
```

## 5. Runner 运行方式

### 5.1 基本用法

EvalRunner 位于 `src/agent/eval/runner.py`，支持批量运行评测。

```python
from src.agent.eval.runner import EvalRunner

runner = EvalRunner()

# 运行 smoke 集评测
results = runner.run(
    dataset_type="smoke",
    top_k=10,
    enable_rewrite=False,
    enable_hybrid=True,
    enable_rerank=False
)

print(f"运行完成: {len(results.cases)} 个样例")
```

### 5.2 完整配置

```python
# 使用完整配置
results = runner.run(
    dataset_type="dev",              # 数据集类型: smoke/dev
    top_k=10,                       # 检索返回数量
    enable_rewrite=False,           # 是否启用 query rewrite
    enable_hybrid=True,             # 是否启用 hybrid retrieval
    enable_rerank=False,            # 是否启用 rerank
    chunk_strategy="default",      # chunk 策略标识
    case_ids=["case_001", "case_002"]  # 可选：只运行特定样例
)
```

### 5.3 命令行用法

```bash
# 运行 smoke 集
python -m src.agent.eval.runner --dataset smoke --top-k 10

# 运行 dev 集
python -m src.agent.eval.runner --dataset dev --top-k 10 --enable-rerank

# 运行特定样例
python -m src.agent.eval.runner --dataset dev --case-ids case_001 case_002
```

### 5.4 比较配置

```python
# 比较两组配置
comparison = runner.compare(
    config_a={
        "enable_hybrid": True,
        "enable_rerank": False
    },
    config_b={
        "enable_hybrid": True,
        "enable_rerank": True
    },
    dataset_type="smoke",
    top_k=10
)

print(f"配置 A Recall: {comparison.config_a_recall}")
print(f"配置 B Recall: {comparison.config_b_recall}")
print(f"差异: {comparison.delta}")
```

## 6. 报告产物说明

### 6.1 Reporter 用法

Reporter 位于 `src/agent/eval/reporter.py`，负责生成评估报告。

```python
from src.agent.eval.reporter import Reporter

reporter = Reporter()

# 生成报告
output_dir = reporter.generate(
    results=results,
    config=run_config,
    output_dir="data/eval/results"
)
```

### 6.2 输出文件

每次运行必须生成独立结果目录，目录命名包含时间戳或 run_id：

```
data/eval/results/
└── run_20260115_143022/
    ├── report.md         # Markdown 格式报告
    ├── metrics.json      # 指标详情 JSON
    └── run_config.json   # 运行时配置
```

### 6.3 report.md 内容

```markdown
# 评估报告

## 运行摘要
- 运行时间: 2026-01-15 14:30:22
- 数据集: smoke
- 样例数: 10
- Top-K: 10

## 检索指标
| 指标 | 值 |
|------|------|
| Recall@10 | 0.85 |
| Hit@10 | 0.90 |
| MRR | 0.82 |
| PageNo Hits | 0.75 |
| SectionTitle Hits | 0.70 |

## 回答指标
| 指标 | 值 |
|------|------|
| 平均回答长度 | 256 |
| 平均引用数 | 3.2 |
| 平均关键词覆盖率 | 0.88 |
| 平均完整度 | 75.0 |

## 详细结果
...
```

### 6.4 metrics.json 结构

```json
{
  "run_id": "run_20260115_143022",
  "timestamp": "2026-01-15T14:30:22",
  "dataset": "smoke",
  "total_cases": 10,
  "retrieval_metrics": {
    "recall_at_k": 0.85,
    "hit_at_k": 0.90,
    "mrr": 0.82,
    "page_no_hits": 0.75,
    "section_title_hits": 0.70
  },
  "answer_metrics": {
    "avg_answer_length": 256,
    "avg_citation_count": 3.2,
    "avg_keyword_coverage": 0.88,
    "avg_completeness": 75.0
  }
}
```

### 6.5 run_config.json 结构

```json
{
  "dataset_type": "smoke",
  "top_k": 10,
  "enable_rewrite": false,
  "enable_hybrid": true,
  "enable_rerank": false,
  "chunk_strategy": "default"
}
```

## 7. 实验结果目录说明

### 7.1 目录结构

```
data/eval/
├── smoke_cases.jsonl          # Smoke 测试集
├── dev_cases.jsonl            # Dev 测试集
└── results/                   # 实验结果目录
    ├── run_20260115_143022/   # 第一次运行
    │   ├── report.md
    │   ├── metrics.json
    │   └── run_config.json
    ├── run_20260116_093045/   # 第二次运行
    │   ├── report.md
    │   ├── metrics.json
    │   └── run_config.json
    └── ...
```

### 7.2 实验对比

不同实验结果保存在不同目录，便于对比：

```bash
# 对比两次实验
ls -la data/eval/results/
# run_20260115_143022  配置A
# run_20260116_093045  配置B
```

## 8. 快速验证命令

```bash
# 验证模块导入
python -c "from src.agent.eval.runner import EvalRunner; print('OK')"
python -c "from src.agent.eval.reporter import Reporter; print('OK')"

# 运行 Phase 10 单元测试
python -m pytest tests/unit/test_eval_dataset.py tests/unit/test_retrieval_eval.py tests/unit/test_answer_eval.py -v

# 运行 Phase 10 集成测试
python -m pytest tests/integration/test_eval_runner.py -v

# 运行 smoke 集评测
python -m src.agent.eval.runner --dataset smoke
```