"""
Search pipeline for agent-level retrieval.

This module provides a unified search pipeline that wraps existing
HybridSearch and reranker components.
"""

import time
from typing import Any, Dict, List, Optional

from ..infra.logging import get_logger
from ..schemas.retrieval import (
    RetrievalCandidate,
    RetrievalConfig,
    RetrievalResult,
    RewriteResult,
)
from .query_rewriter import QueryRewriter
from src.core.query_engine.hybrid_search import HybridSearch, create_hybrid_search
from src.core.query_engine.query_processor import QueryProcessor
from src.core.types import RetrievalResult as CoreRetrievalResult
from src.libs.reranker import RerankerFactory

logger = get_logger(__name__)


class SearchPipeline:
    """Unified search pipeline wrapping existing HybridSearch and reranker.

    This pipeline orchestrates:
    1. Query rewriting (optional)
    2. Hybrid retrieval using existing HybridSearch
    3. Reranking using existing reranker (optional)

    Attributes:
        _config: Retrieval configuration
        _hybrid_search: The underlying HybridSearch instance
        _reranker: The reranker instance
        _rewriter: Query rewriter instance
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        hybrid_search: Optional[HybridSearch] = None,
        settings: Optional[Any] = None,
    ):
        """Initialize SearchPipeline.

        Args:
            config: Retrieval configuration. Creates default if not provided.
            hybrid_search: Optional HybridSearch instance. Created from settings if not provided.
            settings: Application settings for component initialization.
        """
        self._config = config or RetrievalConfig()
        self._settings = settings
        self._hybrid_search = hybrid_search
        self._reranker = None
        self._rewriter = QueryRewriter()

    def _ensure_initialized(self) -> None:
        """Ensure all components are initialized."""
        if self._hybrid_search is None:
            self._initialize_hybrid_search()

        if self._reranker is None and self._config.enable_rerank:
            self._initialize_reranker()

    def _initialize_hybrid_search(self) -> None:
        """Initialize HybridSearch from settings."""
        if self._settings is None:
            from src.core.settings import load_settings

            self._settings = load_settings()

        # Create components needed for HybridSearch
        from src.core.query_engine.dense_retriever import create_dense_retriever
        from src.core.query_engine.sparse_retriever import create_sparse_retriever
        from src.ingestion.storage.bm25_indexer import BM25Indexer
        from src.libs.embedding.embedding_factory import EmbeddingFactory
        from src.libs.vector_store.vector_store_factory import VectorStoreFactory
        from pathlib import Path

        collection = getattr(
            self._settings.vector_store, "collection_name", "knowledge_hub"
        )

        # Create embedding client and vector store
        embedding_client = EmbeddingFactory.create(self._settings)
        vector_store = VectorStoreFactory.create(self._settings)

        # Check collection and fallback if needed
        try:
            coll = vector_store.client.get_collection(collection)
            if coll.count() == 0:
                logger.warning(
                    f"Collection '{collection}' is empty, falling back to 'default'"
                )
                collection = "default"
                vector_store = VectorStoreFactory.create(
                    self._settings, collection_name=collection
                )
        except Exception:
            logger.warning(
                f"Collection '{collection}' not found, trying 'default'"
            )
            collection = "default"
            vector_store = VectorStoreFactory.create(
                self._settings, collection_name=collection
            )

        # Create retrievers
        dense_retriever = create_dense_retriever(
            settings=self._settings,
            embedding_client=embedding_client,
            vector_store=vector_store,
        )

        bm25_indexer = BM25Indexer(
            index_dir=str(Path(f"data/db/bm25/{collection}"))
        )
        sparse_retriever = create_sparse_retriever(
            settings=self._settings,
            bm25_indexer=bm25_indexer,
            vector_store=vector_store,
        )
        sparse_retriever.default_collection = collection

        # Create query processor and hybrid search
        query_processor = QueryProcessor()
        self._hybrid_search = create_hybrid_search(
            settings=self._settings,
            query_processor=query_processor,
            dense_retriever=dense_retriever,
            sparse_retriever=sparse_retriever,
        )

    def _initialize_reranker(self) -> None:
        """Initialize reranker from settings."""
        if self._settings is None:
            from src.core.settings import load_settings

            self._settings = load_settings()

        self._reranker = RerankerFactory.create(self._settings)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        enable_rewrite: Optional[bool] = None,
        enable_hybrid: Optional[bool] = None,
        enable_rerank: Optional[bool] = None,
        return_details: bool = False,
    ) -> RetrievalResult:
        """Execute the search pipeline.

        Args:
            query: Search query
            top_k: Number of results to return
            enable_rewrite: Override query rewrite setting
            enable_hybrid: Override hybrid retrieval setting
            enable_rerank: Override rerank setting
            return_details: Whether to return debug information

        Returns:
            RetrievalResult with candidates and debug trace
        """
        start_time = time.time()

        # Apply overrides
        enable_rewrite = (
            enable_rewrite
            if enable_rewrite is not None
            else self._config.enable_query_rewrite
        )
        enable_hybrid = (
            enable_hybrid if enable_hybrid is not None else self._config.enable_hybrid
        )
        enable_rerank = (
            enable_rerank if enable_rerank is not None else self._config.enable_rerank
        )
        top_k = top_k or self._config.fusion_top_k

        # Ensure components are initialized
        self._ensure_initialized()

        debug_trace: Dict[str, Any] = {}

        # Step 1: Query rewriting
        rewrite_result: Optional[RewriteResult] = None
        if enable_rewrite:
            rewrite_result = self._rewriter.rewrite(query)
            debug_trace["rewritten_queries"] = rewrite_result.rewritten_queries
            debug_trace["keywords"] = rewrite_result.keywords
            debug_trace["filters"] = rewrite_result.filters
            search_query = rewrite_result.rewritten_queries[0] if rewrite_result.rewritten_queries else query
        else:
            search_query = query

        # Step 2: Hybrid retrieval
        dense_results: List[CoreRetrievalResult] = []
        sparse_results: List[CoreRetrievalResult] = []

        try:
            if enable_hybrid:
                # Get detailed results for debug trace
                hybrid_detail_result = self._hybrid_search.search(
                    search_query,
                    top_k=top_k,
                    return_details=True,
                )
                results = hybrid_detail_result.results
                if hasattr(hybrid_detail_result, "dense_results"):
                    dense_results = hybrid_detail_result.dense_results or []
                if hasattr(hybrid_detail_result, "sparse_results"):
                    sparse_results = hybrid_detail_result.sparse_results or []
            else:
                # Fallback to just dense retrieval
                from src.core.query_engine.dense_retriever import DenseRetriever

                dense_retriever = self._hybrid_search._dense_retriever  # type: ignore
                results = dense_retriever.search(search_query, top_k=top_k)
                dense_results = results

            debug_trace["dense_hits"] = len(dense_results)
            debug_trace["sparse_hits"] = len(sparse_results)
            debug_trace["merged_hits"] = len(results)

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return RetrievalResult(
                candidates=[],
                total_hits=0,
                query_time_ms=(time.time() - start_time) * 1000,
                debug_trace=debug_trace,
            )

        # Step 3: Convert to RetrievalCandidate
        candidates = self._convert_to_candidates(results)

        # Step 4: Reranking
        reranked_candidates = candidates
        if enable_rerank and self._reranker is not None:
            try:
                # Convert candidates back to core RetrievalResult for reranker
                core_results = [
                    CoreRetrievalResult(
                        chunk_id=c.chunk_id,
                        score=c.score,
                        text=c.text,
                        metadata=c.metadata,
                    )
                    for c in candidates
                ]

                reranked_results = self._reranker.rerank(
                    query, core_results, min(top_k, self._config.rerank_top_k)
                )

                # Convert back to candidates
                reranked_candidates = self._convert_to_candidates(reranked_results)
                debug_trace["reranked_hits"] = len(reranked_candidates)

            except Exception as e:
                logger.warning(f"Rerank failed, using original order: {e}")

        query_time = (time.time() - start_time) * 1000

        return RetrievalResult(
            candidates=reranked_candidates[:top_k],
            total_hits=len(reranked_candidates),
            query_time_ms=query_time,
            debug_trace=debug_trace,
        )

    def _convert_to_candidates(
        self, results: List[CoreRetrievalResult]
    ) -> List[RetrievalCandidate]:
        """Convert core RetrievalResult to RetrievalCandidate.

        Args:
            results: List of core RetrievalResult

        Returns:
            List of RetrievalCandidate
        """
        candidates = []
        for r in results:
            metadata = r.metadata or {}
            candidates.append(
                RetrievalCandidate(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=r.score,
                    source=metadata.get("source_path", ""),
                    title=metadata.get("title", ""),
                    page_no=metadata.get("page_no"),
                    section_title=metadata.get("section_title"),
                    content_type=metadata.get("content_type", "text"),
                    metadata=metadata,
                )
            )
        return candidates

    def set_config(self, config: RetrievalConfig) -> None:
        """Update retrieval configuration.

        Args:
            config: New retrieval configuration
        """
        self._config = config

    def get_config(self) -> RetrievalConfig:
        """Get current retrieval configuration.

        Returns:
            Current RetrievalConfig
        """
        return self._config
