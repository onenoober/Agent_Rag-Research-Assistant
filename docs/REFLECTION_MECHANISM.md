# 反思机制文档

## 1. 概述

反思机制是科研助手 Agent 三期新增的核心能力，使 Agent 具备自我评估检索结果质量的能力。通过反思节点，Agent 可以评估检索结果是否与问题相关、判断是否有足够信息构建答案、如果不足则提供改进建议。

## 2. 工作流程图

```
planner → tool_executor → reflector → [需要更多? iteration_preparer → planner] 或 [足够? answer_builder]
```

### 流程说明

1. **Planner**: 分析用户查询，决定是否需要使用工具
2. **Tool Executor**: 执行检索工具，获取相关文档
3. **Reflector**: 评估检索结果质量，判断是否足够
4. **Iteration Preparer**: 为下一次迭代准备状态（递增迭代计数、清空工具调用）
5. **Answer Builder**: 基于检索结果构建最终答案

## 3. 配置开关说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| enable_reflection | bool | false | 是否启用反思机制 |
| max_iterations | int | 3 | 最大迭代次数 |
| reflection_timeout | int | 30 | 反思节点超时时间（秒） |

### 3.1 如何启用

在 `config/settings.yaml` 中添加：

```yaml
agent:
  enable_reflection: true
  max_iterations: 3
  reflection_timeout: 30
```

### 3.2 配置读取

配置通过 `src/agent/infra/config.py` 中的 `AgentSettings` 类读取：

```python
from src.agent.infra.config import get_agent_runtime_settings

settings = get_agent_runtime_settings()
print(settings.enable_reflection)  # 是否启用反思
print(settings.max_iterations)     # 最大迭代次数
print(settings.reflection_timeout) # 反思超时时间
```

## 4. 安全保护机制

反思机制实现了多重安全保护：

1. **迭代次数保护**: 最大迭代次数（默认3次）防止无限循环
2. **超时保护**: 反思节点执行超时（默认30秒）自动 fallback
3. **错误处理**: 反思失败时默认不需要更多检索，避免阻塞流程
4. **结果截断**: 限制文档数量（最多5个）和长度（每个最多500字符）
5. **反思结果截断**: 反思结果最多1000字符，避免状态膨胀
6. **改进建议限制**: 最多提取3条改进建议

### 4.1 Fallback 行为

当反思节点发生异常时：
- 超时：设置 `needs_more_retrieval = False`，继续使用当前结果
- 错误：设置 `needs_more_retrieval = False`，记录错误信息后继续

## 5. 使用示例

### 5.1 启用反思机制

```python
from src.agent.graph.builder import AgentGraph

# 方式1：通过配置启用（在 settings.yaml 中设置）
graph = AgentGraph()  # 从配置读取 enable_reflection

# 方式2：显式启用
graph = AgentGraph(enable_reflection=True)

# 方式3：显式禁用
graph = AgentGraph(enable_reflection=False)
```

### 5.2 运行 Agent

```python
import asyncio
from src.agent.graph.builder import AgentGraph

async def main():
    graph = AgentGraph(enable_reflection=True)
    result = await graph.run(
        query="什么是 Transformer 架构？",
        session_id="session-123"
    )
    print(result.answer)

asyncio.run(main())
```

## 6. 状态字段说明

AgentState 中新增的反思相关字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| needs_more_retrieval | bool | False | 反思节点判断是否需要更多检索 |
| reflection_notes | str | "" | 反思节点的评估意见 |
| improvement_suggestions | List[str] | [] | 改进建议列表 |
| reasoning_steps | List[Dict] | [] | 推理步骤记录 |
| iteration_count | int | 0 | 当前迭代次数 |
| max_iterations | int | 3 | 最大迭代次数 |

## 7. 注意事项

1. **性能影响**: 反思机制会增加额外的 LLM 调用，建议在复杂查询时启用
2. **默认关闭**: 反思机制默认关闭，需要在配置中显式启用
3. **迭代监控**: 监控 `iteration_count` 避免过多迭代影响性能
4. **向后兼容**: 不启用反思时，保持原有流程不变
5. **错误恢复**: 任何反思节点异常都不会阻塞主流程

## 8. 调试技巧

### 8.1 查看反思日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# 可以看到 reflection 相关的日志输出
```

### 8.2 检查状态

```python
# 可以在 answer_builder 节点后检查状态
print(state.needs_more_retrieval)  # 是否需要更多检索
print(state.reflection_notes)       # 反思评估意见
print(state.iteration_count)        # 当前迭代次数
print(state.improvement_suggestions) # 改进建议
```

## 9. 常见问题

### Q1: 反思机制会增加响应时间吗？

是的，每次反思需要额外的 LLM 调用。默认超时30秒。建议在简单查询时关闭反思，在复杂研究问题時启用。

### Q2: 如何避免无限循环？

通过 `max_iterations` 配置保护。默认最大3次迭代，达到限制后强制进入答案构建节点。

### Q3: 反思节点失败会阻塞流程吗？

不会。反思节点有完善的错误处理和 fallback 机制，失败时会记录错误并继续使用当前检索结果。

### Q4: 如何调整迭代次数？

在 `config/settings.yaml` 中修改 `max_iterations` 值。建议不超过5次。
