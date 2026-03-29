# 文档解析增强模块

本文档详细说明科研助手 agent 二期新增的文档解析增强模块，包括解析入口、各 parser 实现、chunk 策略、metadata 定义、ingestion 接入方式以及 citation 字段扩展。

## 1. 解析入口说明

文档解析模块的入口是 `src/agent/parsers/__init__.py` 中导出的 `DocumentParser` 类。该类根据文件扩展名自动选择合适的解析器进行处理。

```python
from src.agent.parsers import DocumentParser

# 创建解析器实例
parser = DocumentParser()

# 解析文档
parsed_doc = parser.parse("path/to/document.pdf")
```

`DocumentParser` 支持的文件类型：

- `.pdf` - PDF 文档
- `.txt` - 纯文本文件
- `.md` - Markdown 文件

## 2. 各 parser 说明

### 2.1 基类 BaseParser

所有解析器继承自 `BaseParser` 基类，定义在 `src/agent/parsers/base.py` 中。基类接口：

```python
from abc import ABC, abstractmethod
from src.agent.schemas.document import ParsedDocument

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """解析文件并返回结构化文档"""
        pass
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """检查是否能够解析该文件"""
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """返回支持的文件扩展名列表"""
        pass
```

### 2.2 PDF 解析器 PdfParser

PDF 解析器位于 `src/agent/parsers/pdf_parser.py`，采用「复用现有 + 扩展」策略：

- 核心文本提取逻辑调用现有 `PdfLoader`，不重复开发
- 使用 PyMuPDF 直接读取页面边界，获取逐页信息

主要功能：

- 页码保留（每页单独提取）
- 基础标题检测
- 基础图注/表注识别
- 支持文本型 PDF 解析

```python
from src.agent.parsers.pdf_parser import PdfParser, PdfParserConfig

# 使用默认配置
parser = PdfParser()

# 或使用自定义配置
config = PdfParserConfig(
    extract_headings=True,
    detect_tables=True
)
parser = PdfParser(config=config)

# 解析 PDF
parsed_doc = parser.parse("document.pdf")
```

配置项说明：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| extract_headings | bool | True | 是否提取标题 |
| detect_tables | bool | True | 是否检测表格 |
| detect_captions | bool | True | 是否检测图注/表注 |
| heading_levels | List[int] | [1, 2, 3] | 要检测的标题级别 |

### 2.3 文本解析器 TextParser

文本解析器位于 `src/agent/parsers/text_parser.py`，支持 `.txt` 和 `.md` 文件。

对于 `.md` 文件：

- 优先按标题切分 section
- 识别 Markdown 标题层级（# ## ###）

对于 `.txt` 文件：

- 优先按空行切分段落
- 识别基础段落结构

```python
from src.agent.parsers.text_parser import TextParser

parser = TextParser()

# 解析 Markdown 文件
parsed_doc = parser.parse("document.md")

# 解析文本文件
parsed_doc = parser.parse("document.txt")
```

### 2.4 Chunk 构建器 ChunkBuilder

Chunk 构建器位于 `src/agent/parsers/chunk_builder.py`，直接复用现有 `src/libs/splitter/` 能力，不重复开发切分逻辑。

主要功能：

- 按 section 优先切分
- section 过长时进行二级 chunk
- 支持 overlap 配置
- 输出 `StructuredChunk` 列表

```python
from src.agent.parsers.chunk_builder import ChunkBuilder, ChunkBuilderConfig

# 使用默认配置
builder = ChunkBuilder()

# 或使用自定义配置
config = ChunkBuilderConfig(
    chunk_size=500,
    chunk_overlap=50,
    content_types=["text", "table", "caption"]
)
builder = ChunkBuilder(config=config)

# 从 ParsedDocument 构建 chunks
chunks = builder.build_chunks(parsed_document)
```

配置项说明：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| chunk_size | int | 500 | 每个 chunk 的最大字符数 |
| chunk_overlap | int | 50 | 相邻 chunk 之间的重叠字符数 |
| content_types | List[str] | ["text"] | 支持的内容类型 |

## 3. Chunk 策略说明

### 3.1 默认策略

默认 chunk 策略优先保证引用可读性，策略如下：

1. **Section 优先**：按文档的章节/section 进行切分，保持语义完整性
2. **大小限制**：每个 chunk 不超过 `chunk_size` 个字符
3. **Overlap 保护**：相邻 chunk 之间有 `chunk_overlap` 个字符的重叠，确保上下文连续

### 3.2 内容类型支持

每个 chunk 都有 `content_type` 字段，支持以下类型：

| content_type | 说明 |
|-------------|------|
| text | 普通文本内容 |
| table | 表格内容 |
| caption | 图注/表注内容 |

### 3.3 复用现有 Splitter

Chunk 构建器直接调用 `SplitterFactory.create()` 获得 splitter 实例：

```python
from src.libs.splitter import SplitterFactory

splitter = SplitterFactory.create(settings)
texts = splitter.split_text(section.text)
```

## 4. Metadata 字段定义

所有 chunk metadata 统一为以下字段集合：

```python
from src.agent.schemas.document import ChunkMetadata

metadata = ChunkMetadata(
    source_file="document.pdf",      # 源文件名称
    page_no=3,                        # 页码（从 1 开始）
    section_title="第二章 实验方法",  # 章节标题
    chunk_index=0,                    # chunk 在该 section 内的索引
    char_start=0,                     # 在源文档中的起始字符位置
    char_end=450,                     # 在源文档中的结束字符位置
    content_type="text"              # 内容类型
)
```

字段详细说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| source_file | str | 源文件名称 |
| page_no | int | 页码（从 1 开始），PDF 解析时有效 |
| section_title | str | 章节标题，可为空 |
| chunk_index | int | chunk 在该 section 内的索引 |
| char_start | int | chunk 在源文档中的起始字符位置 |
| char_end | int | chunk 在源文档中的结束字符位置 |
| content_type | str | 内容类型（text/table/caption） |

## 5. Ingestion 接入方式

### 5.1 文档 ingestion 服务

文档 ingestion 服务位于 `src/agent/services/document_ingestion_service.py`，负责将解析后的文档写入索引。

```python
from src.agent.services.document_ingestion_service import DocumentIngestionService

# 创建服务实例
service = DocumentIngestionService()

# 执行 ingestion
result = service.ingest(
    file_path="path/to/document.pdf",
    collection_name="my_collection"
)
```

### 5.2 复用现有 IngestionAdapter

服务内部复用现有 `src/agent/adapters/ingestion_adapter.py`，将 structured metadata 写入索引链路。

```python
# ingestion_service.py 中的关键调用
from src.agent.adapters.ingestion_adapter import IngestionAdapter

adapter = IngestionAdapter()
adapter.ingest(
    chunks=structured_chunks,
    collection=collection_name,
    metadata={"source_file": source_file}
)
```

### 5.3 结构化 metadata 写入

Ingestion 过程中必须保留以下字段，不允许在 adapter 层丢弃：

- page_no
- section_title
- content_type

```python
# 每个 chunk 的 metadata 都会被写入向量数据库
for chunk in chunks:
    vector_store.add(
        documents=[chunk.text],
        metadatas=[chunk.metadata.to_dict()]
    )
```

## 6. Citation 字段扩展说明

### 6.1 现有 Citation 结构

项目已有的 `CitationChunk` 结构定义在 `src/agent/schemas/citation.py`：

```python
from src.agent.schemas.citation import CitationChunk

citation = CitationChunk(
    text="相关段落内容...",
    source="document.pdf",
    score=0.95,
    chunk_id="chunk_123"
)
```

### 6.2 二期扩展字段

在已有 citation 结构基础上，二期支持补充输出以下字段：

```python
citation = CitationChunk(
    text="相关段落内容...",
    source="document.pdf",
    score=0.95,
    chunk_id="chunk_123",
    # 二期新增字段
    page_no=3,                        # 页码
    section_title="第二章 实验方法"   # 章节标题
)
```

### 6.3 Citation 来源

Citation 中的 page_no 和 section_title 来源于解析时生成的 `ChunkMetadata`。在检索返回结果时，会自动携带这些 metadata 字段：

```python
# 检索结果中包含 metadata
results = rag_adapter.search(query="实验方法")

for result in results:
    print(f"来源: {result.source}")
    print(f"页码: {result.metadata.get('page_no')}")      # 输出: 3
    print(f"章节: {result.metadata.get('section_title')}") # 输出: 第二章 实验方法
```

### 6.4 使用示例

在 agent 流程中使用扩展后的 citation：

```python
from src.agent.adapters.rag_adapter import RAGAdapter

rag = RAGAdapter()

# 检索
results = rag.search("什么是机器学习")

# 使用包含 page_no 和 section_title 的 citation
for r in results:
    print(f"引用: {r.text[:100]}...")
    print(f"来源: {r.source}, 页码: {r.metadata.get('page_no')}, 章节: {r.metadata.get('section_title')}")
```

## 7. 快速验证命令

```bash
# 验证模块导入
python -c "from src.agent.parsers.document_parser import DocumentParser; print('OK')"

# 运行 Phase 8 单元测试
python -m pytest tests/unit/test_document_schema.py tests/unit/test_pdf_parser.py tests/unit/test_text_parser.py tests/unit/test_chunk_builder.py -v
```