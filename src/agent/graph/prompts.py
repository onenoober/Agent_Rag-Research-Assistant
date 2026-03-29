"""
LLM prompts for Agent.
"""

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from typing import Any, List, Optional

from src.libs.llm.base_llm import Message


PLANNER_SYSTEM_PROMPT = """You are a research assistant AI. Your task is to analyze user queries and determine whether tool assistance is needed.

Available tools:
- rag_search: Search the knowledge base for relevant information
- file_upload: Upload and index files for later search
- calculator: Perform mathematical calculations

CRITICAL RULES:
1. ALWAYS use rag_search when the user asks about:
   - Content from documents, papers, files
   - Specific information that may be in the knowledge base
   - Titles, authors, topics, concepts from uploaded files
   - Questions that start with "What", "How", "Explain", "Describe" about any topic
   
2. ONLY respond directly without tools for:
   - Simple greetings ("hello", "hi", "how are you")
   - Casual conversation that doesn't require factual information
   - Questions about your capabilities

3. If there was a previous search with no results, you should try again with different search terms!

Response format:
- If tools are needed: Respond with "USE_TOOLS" followed by the tool names and arguments
- If no tools needed: Respond with "NO_TOOLS" followed by your direct response"""


PLANNER_HUMAN_PROMPT = """Current conversation history:
{memory_context}

User query: {query}

Analyze the query and determine if tools are needed. Remember: when in doubt, prefer to use tools rather than guess."""


ANSWER_BUILDER_SYSTEM_PROMPT = """You are a research assistant AI. Your task is to provide accurate, helpful answers based on the retrieved information and conversation context.

Guidelines:
1. Use the retrieved documents to support your answer
2. Cite sources using the provided citations
3. Be concise but comprehensive
4. If the retrieved information doesn't fully answer the question, acknowledge this
5. Maintain a helpful and professional tone"""


ANSWER_BUILDER_HUMAN_PROMPT = """Conversation history:
{memory_context}

Retrieved information:
{docs}

User query: {query}

Please provide a helpful answer based on the retrieved information and conversation context."""


TOOL_SUMMARY_PROMPT = """Summarize the tool execution results in a way that can be used to answer the user's query.

Tool results:
{tool_results}

Provide a concise summary of the key information from these tool executions."""


# ========== 新增：反思机制 Prompt ==========
REFLECTOR_SYSTEM_PROMPT = """You are a research quality evaluator. Your task is to critically assess whether the retrieved information adequately answers the user's research question.

## Your Evaluation Criteria:
1. **Relevance**: Do the documents directly address the query?
2. **Completeness**: Is there missing critical information?
3. **Accuracy**: Does the information seem credible and correct?
4. **Sufficiency**: Do you have enough evidence to form a confident answer?

## Guidelines:
- If the information is sufficient: respond with "ADEQUATE" followed by brief justification
- If needs improvement: respond with "NEEDS_IMPROVEMENT" followed by:
  - What specific information is missing
  - Suggested alternative search queries
  - What aspects need more exploration

Be strict in your evaluation. It's better to acknowledge insufficient information than to provide incomplete answers."""


REFLECTOR_HUMAN_PROMPT = """Research question: {query}

Retrieved documents:
{retrieved_docs}

Evaluate whether you have enough information to provide a high-quality, accurate answer."""


def get_reflector_prompt() -> ChatPromptTemplate:
    """Get the reflector prompt template."""
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(REFLECTOR_SYSTEM_PROMPT),
        HumanMessagePromptTemplate.from_template(REFLECTOR_HUMAN_PROMPT),
    ])
    return prompt | get_llm()


# ========== 新增：增强版 Planner Prompt (V2) ==========
PLANNER_SYSTEM_PROMPT_V2 = """You are a Research Assistant AI with advanced reasoning capabilities.

## Your Thinking Process:
1. **Analyze**: Carefully understand the user's research question
2. **Decompose**: Break down complex questions into sub-questions if needed
3. **Plan**: Determine what information is needed and in what order
4. **Execute**: Select appropriate tools to gather information
5. **Reflect**: Be aware of when you need more information

## Available Tools:
- rag_search: Search academic papers and documents
- file_upload: Upload new research materials
- calculator: Perform mathematical calculations

## Research-Specific Guidelines:
- For literature reviews: search for key concepts, authors, methodologies
- For formulas: identify the specific equation and its context
- For comparisons: gather information on both/all subjects
- For "how/why" questions: search for explanations and mechanisms
- For multi-part questions: address each part systematically

## Response format:
If tools are needed:
  "USE_TOOLS" followed by tool calls with reasoning, e.g.:
  - rag_search(query="Transformer attention mechanism", top_k=3)
  - rag_search(query="RNN sequential processing", top_k=3)

If no tools needed (simple greeting, opinion, etc.):
  "NO_TOOLS" followed by your direct response"""


# 新增：支持改进建议的增强版 Human Prompt
PLANNER_HUMAN_PROMPT_V2 = """Current conversation history:
{memory_context}

User query: {query}

{improvement_context}

Analyze the query and determine if tools are needed.

{reasoning_context}"""


def get_planner_prompt_v2() -> ChatPromptTemplate:
    """Get the enhanced planner prompt template (V2)."""
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(PLANNER_SYSTEM_PROMPT_V2),
        HumanMessagePromptTemplate.from_template(PLANNER_HUMAN_PROMPT_V2),
    ])
    return prompt | get_llm()
# ==========================================


_llm_instance = None

# Prompt 模板缓存
_planner_prompt = None
_planner_prompt_v2 = None
_answer_builder_prompt = None
_reflector_prompt = None
_tool_summary_prompt = None


def get_llm() -> "BaseChatModel":
    """Get the LLM instance for the agent (cached)."""
    global _llm_instance
    if _llm_instance is None:
        from src.libs.llm.llm_factory import LLMFactory
        from src.core.settings import load_settings

        settings = load_settings()
        base_llm = LLMFactory.create(settings)

        # Wrap the custom BaseLLM to be LangChain compatible
        _llm_instance = _LangChainLLMWrapper(base_llm)

    return _llm_instance


class _LangChainLLMWrapper(BaseChatModel):
    """Wrapper to make custom BaseLLM compatible with LangChain's BaseChatModel."""

    model_name: str = "custom-llm"
    llm: Any = None

    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)

    @property
    def _llm_type(self) -> str:
        return "custom_llm_wrapper"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat response."""
        # Convert LangChain messages to custom Message format
        custom_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                custom_messages.append(Message(role="user", content=msg.content))
            elif isinstance(msg, AIMessage):
                custom_messages.append(Message(role="assistant", content=msg.content))
            elif isinstance(msg, SystemMessage):
                custom_messages.append(Message(role="system", content=msg.content))
            else:
                custom_messages.append(Message(role="user", content=str(msg)))

        # Call the custom LLM
        response = self.llm.chat(custom_messages)

        # Convert response back to LangChain format
        ai_message = AIMessage(content=response.content)

        return ChatResult(
            generations=[ChatGeneration(message=ai_message)],
            llm_output={"model": response.model}
        )

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name}


def get_planner_prompt() -> ChatPromptTemplate:
    """Get the planner prompt template (cached)."""
    global _planner_prompt
    if _planner_prompt is None:
        _planner_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(PLANNER_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(PLANNER_HUMAN_PROMPT),
        ])
    return _planner_prompt | get_llm()


def get_planner_prompt_v2() -> ChatPromptTemplate:
    """Get the enhanced planner prompt template (V2, cached)."""
    global _planner_prompt_v2
    if _planner_prompt_v2 is None:
        _planner_prompt_v2 = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(PLANNER_SYSTEM_PROMPT_V2),
            HumanMessagePromptTemplate.from_template(PLANNER_HUMAN_PROMPT_V2),
        ])
    return _planner_prompt_v2 | get_llm()


def get_answer_builder_prompt() -> ChatPromptTemplate:
    """Get the answer builder prompt template (cached)."""
    global _answer_builder_prompt
    if _answer_builder_prompt is None:
        _answer_builder_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(ANSWER_BUILDER_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(ANSWER_BUILDER_HUMAN_PROMPT),
        ])
    return _answer_builder_prompt | get_llm()


def get_reflector_prompt() -> ChatPromptTemplate:
    """Get the reflector prompt template (cached)."""
    global _reflector_prompt
    if _reflector_prompt is None:
        _reflector_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(REFLECTOR_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(REFLECTOR_HUMAN_PROMPT),
        ])
    return _reflector_prompt | get_llm()


def get_tool_summary_prompt() -> ChatPromptTemplate:
    """Get the tool summary prompt template (cached)."""
    global _tool_summary_prompt
    if _tool_summary_prompt is None:
        _tool_summary_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template(TOOL_SUMMARY_PROMPT),
        ])
    return _tool_summary_prompt | get_llm()


def reset_prompt_cache() -> None:
    """Reset all prompt caches (useful for testing)."""
    global _planner_prompt, _planner_prompt_v2
    global _answer_builder_prompt, _reflector_prompt, _tool_summary_prompt
    _planner_prompt = None
    _planner_prompt_v2 = None
    _answer_builder_prompt = None
    _reflector_prompt = None
    _tool_summary_prompt = None
    logger.info("Prompt cache reset")
