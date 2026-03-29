"""Evaluation page for Research Agent.

This page allows users to run evaluations on the agent using smoke/dev datasets
and view the evaluation results.
"""

import streamlit as st
from pathlib import Path
import json
from typing import Dict, Any, Optional

from src.agent.infra.logging import get_logger
from src.agent.eval.dataset import EvalDatasetLoader
from src.agent.eval.runner import AgentEvalRunner
from src.agent.eval.reporter import EvalReporter


logger = get_logger(__name__)


def init_eval_session():
    """Initialize evaluation session state."""
    if "eval_results" not in st.session_state:
        st.session_state.eval_results = None
    if "eval_history" not in st.session_state:
        st.session_state.eval_history = []


def render_eval_header():
    """Render evaluation page header."""
    st.title("📊 Evaluation")
    st.markdown("Run evaluations on your agent using test datasets")


def get_available_datasets() -> Dict[str, str]:
    """Get available evaluation datasets."""
    data_dir = Path("data/eval")
    datasets = {}

    if data_dir.exists():
        for f in data_dir.glob("*.jsonl"):
            datasets[f.stem] = str(f)

    return datasets


def render_dataset_selector() -> tuple[str, str]:
    """Render dataset selector."""
    datasets = get_available_datasets()

    if not datasets:
        st.warning("No evaluation datasets found in data/eval/")
        return None, None

    dataset_type = st.selectbox(
        "Select Dataset",
        options=list(datasets.keys()),
        help="Choose a dataset to evaluate"
    )

    return dataset_type, datasets.get(dataset_type)


def render_eval_config() -> Dict[str, Any]:
    """Render evaluation configuration."""
    st.subheader("⚙️ Evaluation Configuration")

    col1, col2 = st.columns(2)

    with col1:
        top_k = st.slider(
            "Retrieval Top K",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            help="Number of chunks to retrieve per query"
        )

        dataset_type = st.selectbox(
            "Dataset Type",
            options=["smoke", "dev"],
            index=0,
            help="smoke: quick test (5-10 cases), dev: full evaluation (20-50 cases)"
        )

    with col2:
        enable_hybrid = st.checkbox(
            "Enable Hybrid Retrieval",
            value=True,
            help="Use hybrid retrieval (dense + sparse)"
        )

        enable_rerank = st.checkbox(
            "Enable Reranking",
            value=False,
            help="Use reranker to improve ranking"
        )

        enable_query_rewrite = st.checkbox(
            "Enable Query Rewrite",
            value=False,
            help="Rewrite query before retrieval"
        )

    return {
        "top_k": top_k,
        "dataset_type": dataset_type,
        "enable_hybrid": enable_hybrid,
        "enable_rerank": enable_rerank,
        "enable_query_rewrite": enable_query_rewrite,
    }


def run_evaluation(dataset_path: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run evaluation with the given configuration."""
    try:
        # 初始化 runner
        from src.agent.adapters.rag_adapter import RAGAdapter

        rag_adapter = RAGAdapter()

        # 创建评估 runner
        runner = AgentEvalRunner(
            retriever=rag_adapter,
            settings=None
        )

        # 运行评估
        result = runner.run(
            dataset_path=dataset_path,
            top_k=config["top_k"],
            dataset_type=config["dataset_type"],
            enable_query_rewrite=config["enable_query_rewrite"],
            enable_hybrid=config["enable_hybrid"],
            enable_rerank=config["enable_rerank"],
        )

        # 获取报告
        report = runner.reporter.generate_report(result)

        return {
            "status": "success",
            "experiment_id": result.experiment_id,
            "config": config,
            "retrieval_summary": result.retrieval_summary,
            "answer_summary": result.answer_summary,
            "report": report,
            "total_elapsed_ms": result.total_elapsed_ms,
        }

    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


def render_eval_results(results: Dict[str, Any]):
    """Render evaluation results."""
    st.subheader("📈 Evaluation Results")

    if results.get("status") == "error":
        st.error(f"❌ Evaluation failed: {results.get('message')}")
        return

    # 实验信息
    st.markdown(f"**Experiment ID:** {results.get('experiment_id', 'N/A')}")
    st.markdown(f"**Duration:** {results.get('total_elapsed_ms', 0) / 1000:.2f}s")

    # 配置信息
    config = results.get("config", {})
    with st.expander("🔧 Configuration"):
        st.json(config)

    # 检索评估结果
    retrieval_summary = results.get("retrieval_summary")
    if retrieval_summary:
        st.markdown("### 🔍 Retrieval Metrics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Recall@K",
                f"{retrieval_summary.avg_recall:.2%}" if hasattr(retrieval_summary, 'avg_recall') else "N/A"
            )

        with col2:
            st.metric(
                "Hit@K",
                f"{retrieval_summary.avg_hit_rate:.2%}" if hasattr(retrieval_summary, 'avg_hit_rate') else "N/A"
            )

        with col3:
            st.metric(
                "Page No Hits",
                retrieval_summary.total_page_no_hits if hasattr(retrieval_summary, 'total_page_no_hits') else 0
            )

        with col4:
            st.metric(
                "Section Title Hits",
                retrieval_summary.total_section_title_hits if hasattr(retrieval_summary, 'total_section_title_hits') else 0
            )

    # 回答评估结果
    answer_summary = results.get("answer_summary")
    if answer_summary:
        st.markdown("### 💬 Answer Metrics")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Avg Answer Length",
                f"{answer_summary.avg_answer_length:.0f}" if hasattr(answer_summary, 'avg_answer_length') else "N/A"
            )

        with col2:
            st.metric(
                "Avg Citation Count",
                f"{answer_summary.avg_citation_count:.1f}" if hasattr(answer_summary, 'avg_citation_count') else "N/A"
            )

        with col3:
            st.metric(
                "Avg Keyword Coverage",
                f"{answer_summary.avg_keyword_coverage:.2%}" if hasattr(answer_summary, 'avg_keyword_coverage') else "N/A"
            )

    # 详细报告
    report = results.get("report")
    if report:
        with st.expander("📄 Full Report"):
            st.markdown(report.get("summary", "No summary available"))


def render_eval_history():
    """Render evaluation history."""
    if not st.session_state.eval_history:
        st.info("No evaluation history yet. Run an evaluation to see results here.")
        return

    st.subheader("📜 Evaluation History")

    for i, result in enumerate(reversed(st.session_state.eval_history[-5:])):
        with st.expander(f"Run {i+1}: {result.get('experiment_id', 'Unknown')} ({result.get('total_elapsed_ms', 0) / 1000:.1f}s)"):
            if result.get("status") == "error":
                st.error(f"Failed: {result.get('message')}")
            else:
                config = result.get("config", {})
                st.markdown(f"**Dataset:** {config.get('dataset_type', 'N/A')}")
                st.markdown(f"**Top K:** {config.get('top_k', 'N/A')}")
                st.markdown(f"**Hybrid:** {'✅' if config.get('enable_hybrid') else '❌'}")
                st.markdown(f"**Rerank:** {'✅' if config.get('enable_rerank') else '❌'}")

                if st.button("View Details", key=f"view_{i}"):
                    render_eval_results(result)


def render_dataset_preview():
    """Render preview of available datasets."""
    st.subheader("📁 Available Datasets")

    datasets = get_available_datasets()

    if not datasets:
        st.info("No datasets found. Please create datasets in data/eval/")
        return

    for name, path in datasets.items():
        with st.expander(f"📄 {name}"):
            try:
                loader = EvalDatasetLoader()
                test_cases = loader.load(path)
                st.markdown(f"**Path:** `{path}`")
                st.markdown(f"**Total Cases:** {len(test_cases)}")

                # 显示前几个样例
                st.markdown("**Sample Cases:**")
                for tc in test_cases[:3]:
                    st.markdown(f"- **{tc.question}**")
                    if tc.expected_keywords:
                        st.caption(f"  Keywords: {', '.join(tc.expected_keywords[:5])}")
            except Exception as e:
                st.error(f"Failed to load: {e}")


def main():
    """Main evaluation page."""
    init_eval_session()
    render_eval_header()

    # 创建标签页
    tab1, tab2 = st.tabs(["🚀 Run Evaluation", "📜 History"])

    with tab1:
        # 数据集预览
        render_dataset_preview()

        st.markdown("---")

        # 选择数据集
        dataset_type, dataset_path = render_dataset_selector()

        if dataset_path:
            # 评估配置
            config = render_eval_config()

            # 运行按钮
            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button("🚀 Run Evaluation", type="primary", disabled=(dataset_path is None)):
                    with st.spinner("Running evaluation..."):
                        results = run_evaluation(dataset_path, config)

                        if results:
                            st.session_state.eval_results = results
                            st.session_state.eval_history.append(results)

                            if results.get("status") == "success":
                                st.success("✅ Evaluation completed!")
                            else:
                                st.error("❌ Evaluation failed")

                        st.rerun()

            with col2:
                if st.button("🗑️ Clear Results"):
                    st.session_state.eval_results = None
                    st.rerun()

            # 显示结果
            if st.session_state.eval_results:
                render_eval_results(st.session_state.eval_results)

    with tab2:
        render_eval_history()


if __name__ == "__main__":
    main()
