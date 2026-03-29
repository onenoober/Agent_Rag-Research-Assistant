"""
Nodes for Agent LangGraph.

Defines the nodes that process the agent state.
"""

import re
import asyncio
import json
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage

from ..infra.logging import get_logger
from ..schemas.citation import CitationChunk
from .state import AgentState
from .prompts import get_planner_prompt, get_answer_builder_prompt, get_reflector_prompt


logger = get_logger(__name__)

# 预编译的正则表达式
_TOOL_PATTERN1 = re.compile(r'(\w+)\s*\((.*?)\)')
_TOOL_PATTERN2 = re.compile(r'(\w+)\s+(\w+)=["\']([^"\']+)["\']')
_TOOL_PATTERN3 = re.compile(r'(\w+)\s+(\{[^}]+\})')
_ARG_PATTERN = re.compile(r'(\w+)\s*=\s*["\']?([^"\'\),]+)["\']?')

# 支持的工具列表（常量，避免重复定义）
_SUPPORTED_TOOLS = frozenset(['rag_search', 'file_upload', 'calculator'])

# 预导入常用模块（避免在函数中重复导入）
_memory_manager = None
_tool_registry = None
_rag_adapter = None

# 预导入 ToolInput、SearchResult 和 CitationChunk（避免在函数中重复导入）
_ToolInput = None
_SearchResult = None
_CitationChunk = None


def _get_tool_input_class():
    """获取 ToolInput 类（延迟初始化）。"""
    global _ToolInput
    if _ToolInput is None:
        from ..tools.base import ToolInput
        _ToolInput = ToolInput
    return _ToolInput


def _get_search_result_class():
    """获取 SearchResult 类（延迟初始化）。"""
    global _SearchResult
    if _SearchResult is None:
        from ..adapters.rag_adapter import SearchResult
        _SearchResult = SearchResult
    return _SearchResult


def _get_citation_chunk_class():
    """获取 CitationChunk 类（延迟初始化）。"""
    global _CitationChunk
    if _CitationChunk is None:
        from ..schemas.citation import CitationChunk
        _CitationChunk = CitationChunk
    return _CitationChunk


def _get_memory_manager():
    """获取 memory manager（延迟初始化）。"""
    global _memory_manager
    if _memory_manager is None:
        from ..memory.manager import get_memory_manager as gmm
        _memory_manager = gmm()
    return _memory_manager


def _get_tool_registry():
    """获取 tool registry（延迟初始化）。"""
    global _tool_registry
    if _tool_registry is None:
        from ..tools.registry import get_tool_registry as gtr
        _tool_registry = gtr()
    return _tool_registry


def _get_rag_adapter():
    """获取 RAG adapter（延迟初始化）。"""
    global _rag_adapter
    if _rag_adapter is None:
        from ..adapters.rag_adapter import get_rag_adapter as gra
        _rag_adapter = gra()
    return _rag_adapter


def _parse_tool_calls(response: str) -> List[Dict[str, Any]]:
    """Parse tool calls from the planner response (optimized).

    Args:
        response: The planner response containing tool call information.

    Returns:
        List of tool call dictionaries with tool_name and arguments.
    """
    if not response:
        return []

    tool_calls = []
    seen_tools = set()  # 避免重复添加相同的工具调用

    # 快速预检查：如果不包含任何工具关键词，直接返回
    if not any(tool in response.lower() for tool in _SUPPORTED_TOOLS):
        return []

    # Try pattern 3 first (JSON format from LLM)
    for match in _TOOL_PATTERN3.finditer(response):
        tool_name = match.group(1).strip()
        if tool_name not in _SUPPORTED_TOOLS or tool_name in seen_tools:
            continue

        json_str = match.group(2).strip()

        try:
            arguments = json.loads(json_str)
        except json.JSONDecodeError:
            arguments = _parse_arguments(json_str)

        tool_calls.append({
            "tool_name": tool_name,
            "arguments": arguments
        })
        seen_tools.add(tool_name)

    # Try pattern 1 (function call style)
    if len(seen_tools) < len(_SUPPORTED_TOOLS):
        for match in _TOOL_PATTERN1.finditer(response):
            tool_name = match.group(1).strip()
            if tool_name not in _SUPPORTED_TOOLS or tool_name in seen_tools:
                continue

            args_str = match.group(2).strip()
            arguments = _parse_arguments(args_str)

            tool_calls.append({
                "tool_name": tool_name,
                "arguments": arguments
            })
            seen_tools.add(tool_name)

    # Try pattern 2 (key=value style) only if needed
    if not tool_calls:
        for match in _TOOL_PATTERN2.finditer(response):
            tool_name = match.group(1).strip()
            if tool_name not in _SUPPORTED_TOOLS or tool_name in seen_tools:
                continue

            key = match.group(2).strip()
            value = match.group(3).strip()
            arguments = {key: value}

            tool_calls.append({
                "tool_name": tool_name,
                "arguments": arguments
            })
            seen_tools.add(tool_name)

    return tool_calls


def _parse_arguments(args_str: str) -> Dict[str, Any]:
    """Parse arguments from argument string."""
    arguments = {}
    
    if not args_str:
        return arguments
    
    # 使用预编译的正则表达式
    for arg_match in _ARG_PATTERN.finditer(args_str):
        key = arg_match.group(1).strip()
        value = arg_match.group(2).strip().strip('"\'')
        
        # Try to convert to appropriate type
        if value.isdigit():
            arguments[key] = int(value)
        elif value.replace('.', '', 1).isdigit():
            arguments[key] = float(value)
        else:
            arguments[key] = value
    
    return arguments


async def load_memory(state: AgentState) -> AgentState:
    """
    Load conversation history from memory.

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    logger.info(f"Loading memory for session: {state.session_id}")

    memory_manager = _get_memory_manager()
    conversation_history = memory_manager.get_history(
        session_id=state.session_id,
        limit=10
    )

    for msg in conversation_history:
        state.add_message(msg.role, msg.content)

    # Build memory context from conversation history
    if state.messages:
        context_parts = []
        for msg in state.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_parts.append(f"{role}: {content}")
        state.memory_context = "\n".join(context_parts)
    else:
        state.memory_context = ""

    state.add_message("user", state.query)
    state.current_message = {"role": "user", "content": state.query}

    return state


async def planner(state: AgentState) -> AgentState:
    """
    计划是否使用工具以及如何使用。

    增强版：支持利用反思节点的改进建议进行重试。
    支持配置开关，默认行为不受影响。
    """
    logger.info("Running enhanced planner node")

    # 获取配置
    from ..infra.config import get_agent_runtime_settings
    enable_reflection = get_agent_runtime_settings().enable_reflection

    try:
        # 构建 planner 输入
        planner_input = {
            "memory_context": state.memory_context,
            "query": state.query,
            "improvement_context": "",
            "reasoning_context": "",
        }

        # 如果有反思改进建议，将其包含在查询中（仅在启用反思时）
        if enable_reflection and state.improvement_suggestions:
            suggestions_text = "\n".join([
                f"- {s}" for s in state.improvement_suggestions
            ])
            planner_input["improvement_context"] = f"""
=== Previous Search Feedback ===
The previous search was found to be insufficient. Consider these suggestions:
{suggestions_text}
"""
            logger.info(f"Using improvement suggestions: {state.improvement_suggestions}")

        # 如果有推理步骤记录，添加到上下文中
        if enable_reflection and state.reasoning_steps:
            reasoning_text = "\n".join([
                f"- [{step['step']}] {step['name']}: {step['content'][:100]}..."
                for step in state.reasoning_steps[-3:]  # 只取最近3步
            ])
            planner_input["reasoning_context"] = f"""
=== Recent Reasoning Steps ===
{reasoning_text}
"""

        # 记录推理步骤
        if enable_reflection:
            state.reasoning_steps.append({
                "step": "planning",
                "name": "query_analysis",
                "content": f"Analyzing query: {state.query[:100]}..."
            })

        # 选择使用哪个 prompt 版本
        if enable_reflection and state.improvement_suggestions:
            from .prompts import get_planner_prompt_v2
            prompt = get_planner_prompt_v2()
        else:
            prompt = get_planner_prompt()

        messages = await prompt.ainvoke(planner_input)

        # Handle both LangChain message formats
        if hasattr(messages, 'content'):
            response_content = messages.content
        elif hasattr(messages, 'to_string'):
            response_content = messages.to_string()
        else:
            response_content = str(messages)

        if "USE_TOOLS" in response_content.upper():
            state.should_use_tools = True
            state.next_node = "tool_executor"

            # Parse tool calls from the response
            tool_calls = _parse_tool_calls(response_content)
            state.tool_calls = tool_calls

            logger.info(f"Planner decided to use tools: {tool_calls}")

            # 记录推理步骤
            if enable_reflection:
                state.reasoning_steps.append({
                    "step": "planning",
                    "name": "tool_selection",
                    "content": f"Selected tools: {[tc['tool_name'] for tc in tool_calls]}"
                })
        else:
            state.should_use_tools = False
            state.next_node = "answer_builder"
            if "NO_TOOLS" in response_content.upper():
                direct_response = response_content.split("NO_TOOLS")[-1].strip()
                state.answer = direct_response[:500]
            else:
                state.answer = response_content[:500]
            logger.info("Planner decided to respond directly")

    except Exception as e:
        logger.error(f"Planner error: {e}")
        state.error = str(e)
        state.should_use_tools = False
        state.next_node = "answer_builder"

    return state


async def tool_executor(state: AgentState) -> AgentState:
    """
    Execute required tools (optimized with pre-imported classes).

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    logger.info("Running tool executor node")

    # 如果 tool_calls 为空但 query 存在，使用查询作为 fallback
    if not state.tool_calls and state.query:
        logger.info(f"No tool_calls found in state, using query as fallback")
        state.tool_calls = [{
            "tool_name": "rag_search",
            "arguments": {"query": state.query, "top_k": state.top_k}
        }]

    # 检查 tool_calls 中的 arguments 是否为空，如果是则使用 query
    for tc in state.tool_calls:
        arguments = tc.get("arguments", {})
        if not arguments and state.query:
            logger.info(f"Tool {tc.get('tool_name')} has empty arguments, using query as fallback")
            tc["arguments"] = {"query": state.query, "top_k": state.top_k}

    # 使用预缓存的 registry
    registry = _get_tool_registry()

    # 预获取 ToolInput 和 SearchResult 类
    ToolInput = _get_tool_input_class()
    SearchResult = _get_search_result_class()

    try:
        async def execute_single_tool(tool_call: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a single tool and return the result."""
            tool_name = tool_call.get("tool_name")
            arguments = tool_call.get("arguments", {}).copy()

            # Map common parameter aliases to ToolInput schema
            param_mapping = {
                "num_results": "top_k",
                "depth": "top_k",
                "limit": "top_k",
                "n": "top_k",
                "k": "top_k",
            }
            for old_param, new_param in param_mapping.items():
                if old_param in arguments:
                    arguments[new_param] = arguments.pop(old_param)

            tool = registry.get(tool_name)
            if tool:
                # Filter arguments to only include those in the tool's input_schema
                valid_params = set()
                schema = tool.input_schema
                if schema:
                    for param, config in schema.items():
                        valid_params.add(param)
                
                # Only keep valid parameters
                filtered_args = {k: v for k, v in arguments.items() if k in valid_params}
                
                tool_input = ToolInput(**filtered_args)
                result = await tool.execute(tool_input)

                # If it's a RAG search, also return the search results
                search_results = []
                if tool_name == "rag_search" and result.success and result.result:
                    search_results = result.result.get("results", [])

                return {
                    "tool_name": tool_name,
                    "result": str(result),
                    "success": True,
                    "search_results": search_results
                }
            else:
                return {
                    "tool_name": tool_name,
                    "result": "",
                    "success": False,
                    "error": f"Tool {tool_name} not found"
                }

        # 并行执行所有工具
        if len(state.tool_calls) > 1:
            logger.info(f"Executing {len(state.tool_calls)} tools in parallel")
            results = await asyncio.gather(
                *[execute_single_tool(tc) for tc in state.tool_calls],
                return_exceptions=True
            )
        else:
            # 单个工具直接执行
            results = [await execute_single_tool(state.tool_calls[0])]

        # 处理结果（使用预获取的 SearchResult 类）
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Tool execution exception: {r}")
                continue

            tool_name = r.get("tool_name", "")
            if r.get("success"):
                state.add_tool_result(tool_name, r.get("result", ""))

                # 处理 RAG 搜索结果
                for sr in r.get("search_results", []):
                    state.retrieved_docs.append(SearchResult(
                        chunk_id=sr.get("index", "unknown"),
                        text=sr.get("text", ""),
                        score=sr.get("score", 0.0),
                        source=sr.get("source", ""),
                        title=sr.get("title", ""),
                    ))
            else:
                state.add_tool_result(tool_name, "", r.get("error", "Unknown error"))

        state.next_node = "answer_builder"

    except Exception as e:
        logger.error(f"Tool executor error: {e}")
        state.error = str(e)
        state.next_node = "answer_builder"

    return state


async def answer_builder(state: AgentState) -> AgentState:
    """
    Build the final answer.

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    logger.info("Running answer builder node")

    try:
        retrieved_texts = "\n\n".join([doc.text for doc in state.retrieved_docs])

        prompt = get_answer_builder_prompt()
        messages = await prompt.ainvoke({
            "memory_context": state.memory_context,
            "docs": retrieved_texts or "No documents retrieved.",
            "query": state.query,
        })

        # Handle both LangChain message formats
        if hasattr(messages, 'content'):
            answer = messages.content
        elif hasattr(messages, 'to_string'):
            answer = messages.to_string()
        else:
            answer = str(messages)
        
        if len(answer) > 10000:
            answer = answer[:10000]

        state.answer = answer

        # 使用预获取的 CitationChunk 类
        CitationChunk = _get_citation_chunk_class()
        state.citations = [CitationChunk(
            chunk_id=doc.chunk_id,
            text=doc.text,
            source=doc.source,
            title=getattr(doc, 'title', 'Unknown'),
            score=getattr(doc, 'score', 0.0),
            metadata=getattr(doc, 'metadata', {})
        ) for doc in state.retrieved_docs]

    except Exception as e:
        logger.error(f"Answer builder error: {e}")
        state.error = str(e)
        if not state.answer:
            state.answer = "I apologize, but I encountered an error while processing your request."

    return state


async def memory_writer(state: AgentState) -> AgentState:
    """
    Write conversation to memory (optimized with async).

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    logger.info("Running memory writer node")

    from ..memory.manager import get_memory_manager

    try:
        manager = get_memory_manager()
        # 使用异步方法避免阻塞事件循环
        await asyncio.gather(
            manager.add_message_async(state.session_id, "user", state.query),
            manager.add_message_async(state.session_id, "assistant", state.answer),
        )
    except Exception as e:
        logger.error(f"Memory writer error: {e}")

    return state


async def finalize(state: AgentState) -> AgentState:
    """
    Finalize the response.

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    logger.info("Running finalize node")
    state.add_message("assistant", state.answer)
    return state


# ========== 新增：反思节点 ==========
def _extract_improvement_suggestions(response: str) -> List[str]:
    """从反思响应中提取改进建议。"""
    suggestions = []
    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
            suggestions.append(line)
    return suggestions[:3]  # 最多3条建议


async def reflector(state: AgentState) -> AgentState:
    """
    反思节点：评估检索结果质量。

    这是科研助手具备自我评估能力的关键节点。

    ⚠️ 重要安全特性：
    1. 超时保护：30秒超时，超时后默认不需要更多检索
    2. 错误处理：反思失败时默认不需要更多检索，避免阻塞流程
    3. 结果截断：反思结果和文档数量都有长度限制
    """
    logger.info("Running reflector node - self-evaluation")

    # 检查是否需要执行反思（仅在有检索结果时）
    if not state.retrieved_docs:
        state.needs_more_retrieval = True
        state.reflection_notes = "No documents retrieved. Need to try alternative queries."
        state.reasoning_steps.append({
            "step": "reflection",
            "name": "no_docs_check",
            "content": "No retrieval results found"
        })
        return state

    # 构建检索文档摘要（限制长度，避免上下文过长）
    # 只取前5个文档，每个文档最多500字符
    retrieved_texts = "\n\n".join([
        f"[{i+1}] {doc.text[:500]}..."
        for i, doc in enumerate(state.retrieved_docs[:5])
    ])

    try:
        # 获取反思超时配置
        from ..infra.config import get_agent_runtime_settings
        timeout = get_agent_runtime_settings().reflection_timeout

        # 调用 LLM 进行反思评估（带超时保护）
        prompt = get_reflector_prompt()

        # 使用 asyncio.timeout 进行超时保护
        async with asyncio.timeout(timeout):
            messages = await prompt.ainvoke({
                "query": state.query,
                "retrieved_docs": retrieved_texts,
            })

        response = messages.content if hasattr(messages, 'content') else str(messages)

    except asyncio.TimeoutError:
        # 超时时的安全 fallback：默认不需要更多检索
        logger.warning(f"Reflection timeout ({timeout}s), defaulting to adequate")
        state.needs_more_retrieval = False
        state.reflection_notes = f"Reflection timeout ({timeout}s), proceeding with current results"
        state.reasoning_steps.append({
            "step": "reflection",
            "name": "timeout",
            "content": f"Reflection timed out after {timeout}s"
        })
        return state

    except Exception as e:
        # 错误时的安全 fallback：默认不需要更多检索
        logger.error(f"Reflection error: {e}, defaulting to adequate")
        state.needs_more_retrieval = False
        state.reflection_notes = f"Reflection error: {str(e)[:200]}, proceeding with current results"
        state.reasoning_steps.append({
            "step": "reflection",
            "name": "error",
            "content": f"Error during reflection: {str(e)[:100]}"
        })
        return state

    # 记录推理步骤
    state.reasoning_steps.append({
        "step": "reflection",
        "name": "quality_evaluation",
        "content": response[:500]
    })

    # 解析反思结果
    if "NEEDS_IMPROVEMENT" in response.upper():
        state.needs_more_retrieval = True
        # 提取改进建议
        state.improvement_suggestions = _extract_improvement_suggestions(response)
    else:
        state.needs_more_retrieval = False

    # 截断反思结果，避免状态膨胀
    state.reflection_notes = response[:1000]

    return state


async def iteration_preparer(state: AgentState) -> AgentState:
    """
    为下一次迭代准备状态。

    清理策略：
    - 递增 iteration_count：记录当前迭代次数
    - 清空 tool_calls：为新一轮工具调用准备
    - 保留 tool_results：保留历史检索结果供参考
    - 累积 retrieved_docs：保留所有检索到的文档
    - 保留 improvement_suggestions：保留改进建议供 planner 使用

    ⚠️ 重要：这个节点只在启用反思机制时才会被调用
    """
    state.iteration_count += 1
    state.tool_calls = []  # 清空上一轮的工具调用
    # 保留其他状态，让所有信息累积
    logger.info(f"Iteration prepared: count={state.iteration_count}, max={state.max_iterations}")
    return state
# ==========================================
