#!/usr/bin/env python
"""Phoenix 项目 RAG 评估脚本。

支持多种评估模式：
1. 纯检索评估 (hit_rate, mrr)
2. RAGAS 评估 (faithfulness, answer_relevancy, context_precision)
3. 综合评估 (同时运行检索和 RAGAS)

Usage:
    # 激活 conda 环境后运行
    conda activate bigmodel

    # 检索评估 (hit_rate, mrr)
    python scripts/evaluate_phoenix.py --mode retrieval

    # RAGAS 评估 (需要 LLM)
    python scripts/evaluate_phoenix.py --mode ragas

    # 综合评估 (检索 + RAGAS)
    python scripts/evaluate_phoenix.py --mode all

    # 使用自定义测试集
    python scripts/evaluate_phoenix.py --test-set tests/fixtures/phoenix_test_set.json

    # JSON 输出
    python scripts/evaluate_phoenix.py --mode all --json

Exit codes:
    0 - Success
    1 - Partial failure (some evaluations failed)
    2 - Complete failure
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.settings import load_settings
from src.evaluation.evaluators.custom import CustomEvaluator
from src.evaluation.evaluators.ragas import RagasEvaluator
from src.libs.vector_store.vector_store_factory import VectorStoreFactory
from src.libs.embedding.embedding_factory import EmbeddingFactory
from src.core.query_engine.hybrid_search import HybridSearch
from src.core.query_engine.dense_retriever import DenseRetriever
from src.core.query_engine.fusion import RRFFusion
from src.core.query_engine.reranker import CoreReranker
from src.observability.evaluation.eval_runner import EvalRunner, EvalReport
from src.observability.logger import get_logger

logger = get_logger(__name__)


def create_hybrid_search(settings: Any) -> HybridSearch:
    """Create HybridSearch with all necessary components.

    Args:
        settings: Application settings.

    Returns:
        Configured HybridSearch instance.
    """
    # Create vector store
    vector_store = VectorStoreFactory.create(settings)

    # Create embedding client
    embedding_client = EmbeddingFactory.create(settings)

    # Create dense retriever
    dense_retriever = DenseRetriever(
        settings=settings,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    # Get RRF k value from settings
    retrieval_config = getattr(settings, 'retrieval', None)
    rrf_k = 60
    if retrieval_config is not None:
        rrf_k = getattr(retrieval_config, 'rrf_k', 60)

    # Create fusion
    fusion = RRFFusion(k=rrf_k)

    # Create hybrid search
    hybrid_search = HybridSearch(
        settings=settings,
        dense_retriever=dense_retriever,
        fusion=fusion,
    )

    return hybrid_search


# ─────────────────────────────────────────────────────────────────────────────
# Answer Generator for RAGAS
# ─────────────────────────────────────────────────────────────────────────────

def create_answer_generator(settings: Any):
    """Create an answer generator using LLM.

    Args:
        settings: Application settings.

    Returns:
        A callable (query, chunks) -> answer string.
    """
    from src.libs.llm.llm_factory import LLMFactory
    from src.libs.llm.base_llm import Message

    llm = LLMFactory.create(settings)

    def generate(query: str, chunks: List[Any]) -> str:
        """Generate answer from retrieved chunks using LLM."""
        texts = []
        for chunk in chunks[:5]:  # Use top 5 chunks
            if isinstance(chunk, dict):
                text = chunk.get("text") or chunk.get("content") or str(chunk)
            elif hasattr(chunk, "text"):
                text = str(getattr(chunk, "text"))
            else:
                text = str(chunk)
            texts.append(text)

        context = "\n\n".join(texts)

        prompt = f"""根据以下上下文内容，回答用户问题。

上下文：
{context}

问题：{query}

请基于上下文给出准确、完整的回答。如果上下文中没有相关信息，请明确说明。"""

        try:
            response = llm.chat([Message(role="user", content=prompt)])
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"Answer generation failed: {e}")
            return context[:2000]

    return generate


# ─────────────────────────────────────────────────────────────────────────────
# Report Formatter
# ─────────────────────────────────────────────────────────────────────────────

def print_report_summary(report: EvalReport, title: str) -> None:
    """Print a summary of the evaluation report."""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"  评估器: {report.evaluator_name}")
    print(f"  测试用例: {report.query_count}")
    print(f"  总耗时: {report.total_elapsed_ms / 1000:.1f} 秒")
    print()
    print("  聚合指标:")
    for metric, value in report.aggregate_metrics.items():
        bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
        print(f"    {metric:20s} [{bar}] {value:.4f}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main Evaluation
# ─────────────────────────────────────────────────────────────────────────────

async def run_evaluation(
    settings: Any,
    test_set_path: str,
    mode: str,
    top_k: int,
    collection: str,
    output_json: bool,
    verbose: bool,
) -> int:
    """Run the evaluation based on mode."""
    print("[*] 初始化检索组件...")

    try:
        hybrid_search = create_hybrid_search(settings)
        reranker = CoreReranker(settings=settings)
        print("[OK] 检索组件初始化成功")
    except Exception as e:
        print(f"[FAIL] 检索组件初始化失败: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 2

    retrieval_report: Optional[EvalReport] = None
    ragas_report: Optional[EvalReport] = None

    # ─── Retrieval Evaluation ────────────────────────────────────────────────
    if mode in ("retrieval", "all"):
        print("\n[*] 运行检索评估 (hit_rate, mrr)...")

        try:
            retrieval_evaluator = CustomEvaluator(
                settings=settings,
                metrics=["hit_rate", "mrr"],
            )

            retrieval_runner = EvalRunner(
                settings=settings,
                hybrid_search=hybrid_search,
                evaluator=retrieval_evaluator,
                reranker=reranker,
                max_concurrency=5,
            )

            retrieval_report = await retrieval_runner.run_async(
                test_set_path=test_set_path,
                top_k=top_k,
                collection=collection,
            )

            print_report_summary(retrieval_report, "检索评估结果")

        except Exception as e:
            print(f"[FAIL] 检索评估失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    # ─── RAGAS Evaluation ────────────────────────────────────────────────────
    if mode in ("ragas", "all"):
        print("\n[*] 运行 RAGAS 评估 (faithfulness, answer_relevancy, context_precision)...")
        print("    注意: RAGAS 评估需要调用 LLM API，请耐心等待...")

        try:
            ragas_evaluator = RagasEvaluator(
                settings=settings,
                metrics=["faithfulness", "answer_relevancy", "context_precision"],
            )
            answer_generator = create_answer_generator(settings)

            ragas_runner = EvalRunner(
                settings=settings,
                hybrid_search=hybrid_search,
                evaluator=ragas_evaluator,
                answer_generator=answer_generator,
                reranker=reranker,
                max_concurrency=2,
            )

            ragas_report = await ragas_runner.run_async(
                test_set_path=test_set_path,
                top_k=top_k,
                collection=collection,
            )

            print_report_summary(ragas_report, "RAGAS 评估结果")

        except Exception as e:
            print(f"[FAIL] RAGAS 评估失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    # ─── Output Report ───────────────────────────────────────────────────────
    if output_json:
        output = {
            "retrieval": retrieval_report.to_dict() if retrieval_report else None,
            "ragas": ragas_report.to_dict() if ragas_report else None,
        }
        print("\n[JSON 输出]")
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 70)
        print("PHOENIX RAG 评估报告")
        print("=" * 70)

        if retrieval_report:
            print(f"\n【检索评估指标】")
            print(f"  评估器: {retrieval_report.evaluator_name}")
            print(f"  测试用例数: {retrieval_report.query_count}")
            print(f"  总耗时: {retrieval_report.total_elapsed_ms / 1000:.1f}s")
            print("\n  指标结果:")
            for metric, value in retrieval_report.aggregate_metrics.items():
                print(f"    - {metric}: {value:.4f}")

        if ragas_report:
            print(f"\n【RAGAS 评估指标】")
            print(f"  评估器: {ragas_report.evaluator_name}")
            print(f"  测试用例数: {ragas_report.query_count}")
            print(f"  总耗时: {ragas_report.total_elapsed_ms / 1000:.1f}s")
            print("\n  指标结果:")
            for metric, value in ragas_report.aggregate_metrics.items():
                print(f"    - {metric}: {value:.4f}")

        print("\n" + "=" * 70)

    # Determine exit code
    if retrieval_report and ragas_report:
        return 0
    elif retrieval_report or ragas_report:
        return 1
    else:
        return 2


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Phoenix 项目 RAG 评估脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--test-set", "-t",
        default="tests/fixtures/phoenix_test_set.json",
        help="测试集路径 (默认: tests/fixtures/phoenix_test_set.json)"
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["retrieval", "ragas", "all"],
        default="all",
        help="评估模式: retrieval=检索指标, ragas=RAGAS指标, all=全部 (默认: all)"
    )

    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=10,
        help="检索返回的 chunk 数量 (默认: 10)"
    )

    parser.add_argument(
        "--collection", "-c",
        default="default",
        help="向量数据库集合名称 (默认: default)"
    )

    parser.add_argument(
        "--config",
        default=str(project_root / "config" / "settings.yaml"),
        help="配置文件路径 (默认: config/settings.yaml)"
    )

    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="输出 JSON 格式结果"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出模式"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    print("[*] Phoenix RAG 评估脚本")
    print("=" * 60)
    print(f"  测试集: {args.test_set}")
    print(f"  评估模式: {args.mode}")
    print(f"  Top-K: {args.top_k}")
    print(f"  集合: {args.collection}")
    print("=" * 60)

    # Load settings
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"[FAIL] 配置文件不存在: {config_path}")
            return 2

        settings = load_settings(str(config_path))
        print(f"[OK] 配置加载成功")

    except Exception as e:
        print(f"[FAIL] 配置加载失败: {e}")
        return 2

    # Check test set exists
    test_set_path = Path(args.test_set)
    if not test_set_path.exists():
        print(f"[FAIL] 测试集不存在: {test_set_path}")
        return 2

    # Run evaluation
    try:
        exit_code = asyncio.run(
            run_evaluation(
                settings=settings,
                test_set_path=str(test_set_path),
                mode=args.mode,
                top_k=args.top_k,
                collection=args.collection,
                output_json=args.json,
                verbose=args.verbose,
            )
        )
        return exit_code

    except KeyboardInterrupt:
        print("\n[INFO] 用户中断评估")
        return 130
    except Exception as e:
        print(f"[FAIL] 评估过程出错: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
