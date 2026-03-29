#!/usr/bin/env python
"""简单的评估测试脚本 - 验证 EvalRunner 的组合答案策略。

这个脚本测试：
1. 优先使用 answer_overrides (reference_answer)
2. 如果没有 overrides，使用 answer_generator
3. 评估流程是否正常运行
"""

import asyncio
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.observability.evaluation.eval_runner import (
    EvalRunner,
    load_test_set,
    load_test_set_with_overrides,
)


def test_load_test_set():
    """测试测试集加载功能"""
    print("\n" + "=" * 60)
    print("测试 1: 加载测试集")
    print("=" * 60)

    test_set_path = project_root / "tests" / "fixtures" / "phoenix_test_set_small.json"
    print(f"测试集路径: {test_set_path}")

    test_cases = load_test_set(test_set_path)
    print(f"加载的测试用例数: {len(test_cases)}")

    for i, tc in enumerate(test_cases):
        print(f"\n用例 {i + 1}:")
        print(f"  query: {tc.query[:50]}...")
        print(f"  expected_chunk_ids: {tc.expected_chunk_ids}")
        print(f"  reference_answer: {tc.reference_answer[:50] if tc.reference_answer else 'None'}...")

    return test_cases


def test_load_test_set_with_overrides():
    """测试带 overrides 的测试集加载功能"""
    print("\n" + "=" * 60)
    print("测试 2: 加载测试集并提取 answer_overrides")
    print("=" * 60)

    test_set_path = project_root / "tests" / "fixtures" / "phoenix_test_set_small.json"
    test_cases, overrides = load_test_set_with_overrides(test_set_path)

    print(f"测试用例数: {len(test_cases)}")
    print(f"提取的 overrides 数: {len(overrides)}")

    for idx, answer in overrides.items():
        print(f"\nOverride[{idx}]:")
        print(f"  Answer: {answer[:80]}...")

    return test_cases, overrides


def create_mock_answer_generator():
    """创建一个模拟的答案生成器"""
    def generate(query: str, chunks):
        print(f"    [Mock Generator] 为查询生成答案: {query[:40]}...")
        print(f"    [Mock Generator] 检索到的 chunks 数: {len(chunks) if chunks else 0}")
        return f"[模拟生成的答案] 基于 {len(chunks) if chunks else 0} 个 chunks 回答: {query}"
    return generate


def create_mock_evaluator():
    """创建一个模拟的评估器"""
    from src.evaluation.evaluators.base import BaseEvaluator

    class MockEvaluator(BaseEvaluator):
        def evaluate(
            self,
            query: str,
            retrieved_chunks,
            generated_answer=None,
            ground_truth=None,
            trace=None,
            **kwargs
        ):
            print(f"    [Mock Evaluator] 评估查询: {query[:40]}...")
            print(f"    [Mock Evaluator] 生成的答案: {generated_answer[:50] if generated_answer else 'None'}...")
            print(f"    [Mock Evaluator] 预期 chunk IDs: {ground_truth.get('ids') if ground_truth else 'None'}")

            # 返回模拟的指标
            return {
                "hit_rate": 1.0,
                "mrr": 0.5,
                "custom_metric": 0.95,
            }

    return MockEvaluator()


def create_mock_hybrid_search():
    """创建一个模拟的 HybridSearch"""
    class MockHybridSearch:
        def search(self, query, top_k=10):
            print(f"    [Mock Search] 搜索查询: {query[:40]}...")
            # 返回模拟的检索结果
            return [
                {"id": "chunk_001", "text": "这是第一个检索到的 chunk。"},
                {"id": "chunk_002", "text": "这是第二个检索到的 chunk。"},
                {"id": "chunk_003", "text": "这是第三个检索到的 chunk。"},
            ]

    return MockHybridSearch()


def test_combined_strategy():
    """测试组合策略"""
    print("\n" + "=" * 60)
    print("测试 3: 组合策略测试")
    print("=" * 60)

    test_set_path = project_root / "tests" / "fixtures" / "phoenix_test_set_small.json"

    # 创建模拟组件
    mock_evaluator = create_mock_evaluator()
    mock_search = create_mock_hybrid_search()
    mock_generator = create_mock_answer_generator()

    # 测试场景 1: 只有 answer_overrides（没有 answer_generator）
    print("\n--- 场景 1: 使用 answer_overrides（无 answer_generator）---")
    runner1 = EvalRunner(
        evaluator=mock_evaluator,
        hybrid_search=mock_search,
        answer_generator=None,  # 没有 generator
        answer_overrides={0: "[手动设置的 Override 答案]"},
    )

    async def run_test1():
        report = await runner1.run_async(str(test_set_path), top_k=3)
        print(f"\n场景 1 结果:")
        print(f"  聚合指标: {report.aggregate_metrics}")
        print(f"  查询数: {report.query_count}")
        for qr in report.query_results:
            print(f"  - 答案来源: {'Override' if qr.query in str(qr.generated_answer) else 'Generator'}")
            print(f"  - 生成答案: {qr.generated_answer[:60]}...")

    asyncio.run(run_test1())

    # 测试场景 2: 有 answer_generator 且 auto_build_overrides=True（默认）
    print("\n--- 场景 2: answer_generator + auto_build_overrides=True ---")
    runner2 = EvalRunner(
        evaluator=mock_evaluator,
        hybrid_search=mock_search,
        answer_generator=mock_generator,
        answer_overrides={},  # 空的 overrides
    )

    async def run_test2():
        report = await runner2.run_async(str(test_set_path), top_k=3)
        print(f"\n场景 2 结果:")
        print(f"  聚合指标: {report.aggregate_metrics}")
        print(f"  查询数: {report.query_count}")
        for qr in report.query_results:
            is_override = "[手动设置的 Override 答案]" in (qr.generated_answer or "")
            is_reference = "[模拟生成的答案]" in (qr.generated_answer or "")
            source = "Manual Override" if is_override else ("Reference Answer" if not is_reference else "LLM Generator")
            print(f"  - 答案来源: {source}")
            print(f"  - 生成答案: {qr.generated_answer[:60]}...")

    asyncio.run(run_test2())

    # 测试场景 3: 既有手动 overrides 也有 auto_build_overrides
    print("\n--- 场景 3: 手动 overrides + auto_build_overrides ---")
    runner3 = EvalRunner(
        evaluator=mock_evaluator,
        hybrid_search=mock_search,
        answer_generator=mock_generator,
        answer_overrides={0: "[手动设置的 Override 答案 - 优先级更高]"},  # 会覆盖 auto-built
    )

    async def run_test3():
        report = await runner3.run_async(str(test_set_path), top_k=3)
        print(f"\n场景 3 结果:")
        print(f"  聚合指标: {report.aggregate_metrics}")
        for qr in report.query_results:
            is_manual = "[手动设置的 Override 答案]" in (qr.generated_answer or "")
            is_reference = "[参考答案]" in (qr.generated_answer or "")
            source = "Manual Override" if is_manual else ("Reference Answer" if is_reference else "LLM Generator")
            print(f"  - 答案来源: {source}")
            print(f"  - 生成答案: {qr.generated_answer[:60]}...")

    asyncio.run(run_test3())

    # 测试场景 4: 禁用 auto_build_overrides
    print("\n--- 场景 4: 禁用 auto_build_overrides ---")
    runner4 = EvalRunner(
        evaluator=mock_evaluator,
        hybrid_search=mock_search,
        answer_generator=mock_generator,
        answer_overrides={},  # 空的 overrides
    )

    async def run_test4():
        report = await runner4.run_async(str(test_set_path), top_k=3, auto_build_overrides=False)
        print(f"\n场景 4 结果:")
        print(f"  聚合指标: {report.aggregate_metrics}")
        for qr in report.query_results:
            is_mock = "[模拟生成的答案]" in (qr.generated_answer or "")
            source = "LLM Generator" if is_mock else "Unknown"
            print(f"  - 答案来源: {source}")
            print(f"  - 生成答案: {qr.generated_answer[:60]}...")

    asyncio.run(run_test4())


def main():
    """主函数"""
    print("=" * 60)
    print("EvalRunner 组合策略测试")
    print("=" * 60)

    try:
        # 测试 1: 加载测试集
        test_load_test_set()

        # 测试 2: 加载测试集并提取 overrides
        test_load_test_set_with_overrides()

        # 测试 3: 组合策略测试
        test_combined_strategy()

        print("\n" + "=" * 60)
        print("所有测试完成!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
