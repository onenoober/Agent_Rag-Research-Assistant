"""
RAG adapter for Agent.

Wraps existing RAG retrieval functionality.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import traceback

from ..infra.logging import get_logger
from .settings_adapter import get_agent_config
from ..schemas.retrieval import RetrievalConfig
from ..retrieval.search_pipeline import SearchPipeline
from src.core.query_engine.formula_enhancer import FormulaSearchEnhancer, EnhancedSearchResult


logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Unified search result from RAG adapter."""

    chunk_id: str
    text: str
    score: float
    source: str = ""
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "source": self.source,
            "title": self.title,
            "metadata": self.metadata,
        }


class RAGAdapter:
    """Adapter for RAG retrieval operations."""

    # 类级别组件缓存（跨实例共享）
    _class_embedding_client = None
    _class_vector_store = None
    _class_dense_retriever = None
    _class_sparse_retriever = None
    _class_query_processor = None
    _class_hybrid_search = None

    def __init__(self, collection: Optional[str] = None):
        self._initialized = False
        self._hybrid_search = None
        self._config = get_agent_config()
        # Enhanced retrieval configuration
        self._search_pipeline = None
        self._enable_query_rewrite = False
        self._enable_hybrid = True
        self._enable_rerank = False
        # Formula enhancement
        self._formula_enhancer = None
        self._enable_formula_enhancement = False
        # Override collection
        self._collection_override = collection

    def initialize(self) -> None:
        """Initialize RAG components with component-level caching."""
        if self._initialized:
            # 检查类级别缓存，如果有则直接复用
            if RAGAdapter._class_hybrid_search is not None:
                self._hybrid_search = RAGAdapter._class_hybrid_search
                logger.info("RAG adapter using cached hybrid_search")
                return

        try:
            from src.core.settings import load_settings
            from src.core.query_engine.query_processor import QueryProcessor
            from src.core.query_engine.hybrid_search import create_hybrid_search
            from src.core.query_engine.dense_retriever import create_dense_retriever
            from src.core.query_engine.sparse_retriever import create_sparse_retriever
            from src.ingestion.storage.bm25_indexer import BM25Indexer
            from src.libs.embedding.embedding_factory import EmbeddingFactory
            from src.libs.vector_store.vector_store_factory import VectorStoreFactory
            from pathlib import Path

            # Load settings from config file
            settings = load_settings()

            # Get collection name from config, or use override
            if self._collection_override:
                collection = self._collection_override
            else:
                collection = getattr(settings.vector_store, 'collection_name', 'knowledge_hub')

            # 使用类级别缓存的组件
            if RAGAdapter._class_embedding_client is None:
                RAGAdapter._class_embedding_client = EmbeddingFactory.create(settings)
                logger.debug("Created and cached embedding_client")

            embedding_client = RAGAdapter._class_embedding_client

            # Check if we need to create vector store for this collection
            if RAGAdapter._class_vector_store is None or collection != getattr(RAGAdapter._class_vector_store, 'collection_name', 'default'):
                # Create vector store
                vector_store = VectorStoreFactory.create(settings, collection_name=collection)

                # Check if configured collection has data, fallback to 'default' if empty
                try:
                    coll = vector_store.client.get_collection(collection)
                    if coll.count() == 0:
                        logger.warning(f"Collection '{collection}' is empty, falling back to 'default'")
                        collection = "default"
                        vector_store = VectorStoreFactory.create(settings, collection_name=collection)
                except Exception:
                    logger.warning(f"Collection '{collection}' not found, trying 'default'")
                    collection = "default"
                    vector_store = VectorStoreFactory.create(settings, collection_name=collection)

                RAGAdapter._class_vector_store = vector_store
                RAGAdapter._class_vector_store.collection_name = collection
                logger.debug(f"Created and cached vector_store for collection: {collection}")
            else:
                vector_store = RAGAdapter._class_vector_store
                collection = vector_store.collection_name

            # 复用 dense retriever
            if RAGAdapter._class_dense_retriever is None:
                RAGAdapter._class_dense_retriever = create_dense_retriever(
                    settings=settings,
                    embedding_client=embedding_client,
                    vector_store=vector_store,
                )
                logger.debug("Created and cached dense_retriever")

            dense_retriever = RAGAdapter._class_dense_retriever

            # Create BM25 indexer and sparse retriever
            if RAGAdapter._class_sparse_retriever is None:
                bm25_indexer = BM25Indexer(index_dir=str(Path(f"data/db/bm25/{collection}")))
                sparse_retriever = create_sparse_retriever(
                    settings=settings,
                    bm25_indexer=bm25_indexer,
                    vector_store=vector_store,
                )
                sparse_retriever.default_collection = collection
                RAGAdapter._class_sparse_retriever = sparse_retriever
                logger.debug("Created and cached sparse_retriever")
            else:
                sparse_retriever = RAGAdapter._class_sparse_retriever

            # 复用 query processor
            if RAGAdapter._class_query_processor is None:
                RAGAdapter._class_query_processor = QueryProcessor()
                logger.debug("Created and cached query_processor")

            query_processor = RAGAdapter._class_query_processor

            # 创建 HybridSearch 并缓存
            if RAGAdapter._class_hybrid_search is None:
                RAGAdapter._class_hybrid_search = create_hybrid_search(
                    settings=settings,
                    query_processor=query_processor,
                    dense_retriever=dense_retriever,
                    sparse_retriever=sparse_retriever,
                )
                logger.debug("Created and cached hybrid_search")

            self._hybrid_search = RAGAdapter._class_hybrid_search

            self._initialized = True
            logger.info("RAG adapter initialized successfully with component caching")
        except Exception as e:
            logger.error(f"Failed to initialize RAG adapter: {e}")
            logger.debug(traceback.format_exc())
            raise
        except Exception as e:
            logger.error(f"Failed to initialize RAG adapter: {e}")
            logger.debug(traceback.format_exc())
            raise

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search knowledge base.

        Args:
            query: Search query
            top_k: Number of results to return
            session_id: Optional session ID for tracking

        Returns:
            List of SearchResult objects
        """
        if not self._initialized:
            self.initialize()

        if top_k is None:
            top_k = self._config.retrieval_top_k

        try:
            results = self._hybrid_search.search(query, top_k=top_k)

            search_results = []
            for r in results:
                search_results.append(
                    SearchResult(
                        chunk_id=r.chunk_id,
                        text=r.text,
                        score=r.score,
                        source=r.metadata.get("source_path", ""),
                        title=r.metadata.get("title", ""),
                        metadata=r.metadata,
                    )
                )

            logger.info(f"Search completed: query='{query}', results={len(search_results)}")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            logger.debug(traceback.format_exc())
            return []

    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Retrieve records by their IDs.

        This method is used for cross-reference lookups to fetch
        chunk content given their IDs.

        Args:
            ids: List of chunk IDs to retrieve.

        Returns:
            List of SearchResult objects in the same order as input IDs.
            Empty SearchResult is returned for IDs not found.
        """
        if not self._initialized:
            self.initialize()

        if not ids:
            return []

        try:
            # Access the vector store through the hybrid search components
            # The HybridSearch has dense_retriever attribute
            if hasattr(self._hybrid_search, 'dense_retriever'):
                vector_store = self._hybrid_search.dense_retriever.vector_store
            else:
                logger.warning("Cannot access vector store for get_by_ids")
                return []

            # Use vector store's get_by_ids method
            records = vector_store.get_by_ids(ids)
            
            results = []
            for record in records:
                if record:  # Skip empty records
                    metadata = record.get('metadata', {})
                    results.append(SearchResult(
                        chunk_id=record.get('id', ''),
                        text=record.get('text', ''),
                        score=0.0,  # No score for ID lookup
                        source=metadata.get('source_path', ''),
                        title=metadata.get('title', ''),
                        metadata=metadata,
                    ))
                else:
                    # Add empty result for not found
                    results.append(SearchResult(
                        chunk_id='',
                        text='',
                        score=0.0,
                    ))

            logger.debug(f"get_by_ids completed: requested={len(ids)}, found={len(results)}")
            return results

        except Exception as e:
            logger.error(f"get_by_ids failed: {e}")
            logger.debug(traceback.format_exc())
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        Check RAG adapter health.

        Returns:
            Health status dict
        """
        status = {
            "initialized": self._initialized,
            "config": {
                "vector_store_provider": self._config.vector_store_provider,
                "vector_store_collection": self._config.vector_store_collection,
                "retrieval_top_k": self._config.retrieval_top_k,
            },
        }

        try:
            if self._initialized and self._hybrid_search:
                status["status"] = "healthy"
            else:
                status["status"] = "not_initialized"
        except Exception as e:
            status["status"] = "unhealthy"
            status["error"] = str(e)

        return status

    def search_enhanced(
        self,
        query: str,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        enable_query_rewrite: Optional[bool] = None,
        enable_hybrid: Optional[bool] = None,
        enable_rerank: Optional[bool] = None,
    ) -> List[SearchResult]:
        """
        Search knowledge base with enhanced retrieval pipeline.

        This method uses the new SearchPipeline with configurable options
        for query rewriting, hybrid retrieval, and reranking.

        Args:
            query: Search query
            top_k: Number of results to return
            session_id: Optional session ID for tracking
            enable_query_rewrite: Override query rewrite setting
            enable_hybrid: Override hybrid retrieval setting
            enable_rerank: Override rerank setting

        Returns:
            List of SearchResult objects
        """
        # Initialize search pipeline if needed
        if self._search_pipeline is None:
            self._initialize_search_pipeline()

        # Apply overrides
        rewrite = (
            enable_query_rewrite
            if enable_query_rewrite is not None
            else self._enable_query_rewrite
        )
        hybrid = (
            enable_hybrid if enable_hybrid is not None else self._enable_hybrid
        )
        rerank = (
            enable_rerank if enable_rerank is not None else self._enable_rerank
        )

        if top_k is None:
            top_k = self._config.retrieval_top_k

        try:
            # Execute enhanced search
            result = self._search_pipeline.search(
                query=query,
                top_k=top_k,
                enable_rewrite=rewrite,
                enable_hybrid=hybrid,
                enable_rerank=rerank,
                return_details=True,
            )

            # Convert to SearchResult format
            search_results = []
            for candidate in result.candidates:
                search_results.append(
                    SearchResult(
                        chunk_id=candidate.chunk_id,
                        text=candidate.text,
                        score=candidate.score,
                        source=candidate.source,
                        title=candidate.title,
                        metadata=candidate.metadata,
                    )
                )

            logger.info(
                f"Enhanced search completed: query='{query}', "
                f"results={len(search_results)}, "
                f"dense_hits={result.debug_trace.get('dense_hits', 0)}, "
                f"sparse_hits={result.debug_trace.get('sparse_hits', 0)}"
            )
            return search_results

        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            logger.debug(traceback.format_exc())
            return []

    def _initialize_search_pipeline(self) -> None:
        """Initialize the enhanced search pipeline."""
        try:
            from src.core.settings import load_settings

            settings = load_settings()
            config = RetrievalConfig.from_settings(settings)
            # Apply instance-level overrides
            config.enable_query_rewrite = self._enable_query_rewrite
            config.enable_hybrid = self._enable_hybrid
            config.enable_rerank = self._enable_rerank

            # 复用已初始化的 _hybrid_search，避免重复创建
            self._search_pipeline = SearchPipeline(
                config=config,
                settings=settings,
                hybrid_search=self._hybrid_search  # 复用已有组件
            )
            logger.info("Search pipeline initialized successfully (reusing hybrid_search)")
        except Exception as e:
            logger.error(f"Failed to initialize search pipeline: {e}")
            raise

    def set_enhanced_config(
        self,
        enable_query_rewrite: bool = False,
        enable_hybrid: bool = True,
        enable_rerank: bool = False,
    ) -> None:
        """
        Configure enhanced retrieval options.

        Args:
            enable_query_rewrite: Enable query rewriting
            enable_hybrid: Enable hybrid retrieval (dense + sparse)
            enable_rerank: Enable reranking
        """
        self._enable_query_rewrite = enable_query_rewrite
        self._enable_hybrid = enable_hybrid
        self._enable_rerank = enable_rerank

        # Update pipeline config if already initialized
        if self._search_pipeline is not None:
            config = self._search_pipeline.get_config()
            config.enable_query_rewrite = enable_query_rewrite
            config.enable_hybrid = enable_hybrid
            config.enable_rerank = enable_rerank
            self._search_pipeline.set_config(config)

        logger.info(
            f"Enhanced config updated: rewrite={enable_query_rewrite}, "
            f"hybrid={enable_hybrid}, rerank={enable_rerank}"
        )

    def get_enhanced_config(self) -> Dict[str, Any]:
        """Get current enhanced retrieval configuration."""
        return {
            "enable_query_rewrite": self._enable_query_rewrite,
            "enable_hybrid": self._enable_hybrid,
            "enable_rerank": self._enable_rerank,
        }
    
    def _get_formula_enhancer(self) -> FormulaSearchEnhancer:
        """Get or create formula enhancer."""
        if self._formula_enhancer is None:
            self._formula_enhancer = FormulaSearchEnhancer(rag_adapter=self)
        return self._formula_enhancer
    
    def set_formula_enhancement(
        self,
        enable: bool = True,
        enable_detection: bool = True,
        enable_cross_reference: bool = True,
    ) -> None:
        """Enable or configure formula enhancement.
        
        Args:
            enable: Whether to enable formula enhancement
            enable_detection: Auto-detect formulas in queries
            enable_cross_reference: Find related chunks via formula mapping
        """
        self._enable_formula_enhancement = enable
        if enable:
            enhancer = self._get_formula_enhancer()
            enhancer.enable_formula_detection = enable_detection
            enhancer.enable_cross_reference = enable_cross_reference
            logger.info(
                f"Formula enhancement enabled: detection={enable_detection}, "
                f"cross_ref={enable_cross_reference}"
            )
    
    def search_with_formula_enhancement(
        self,
        query: str,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search with formula-aware enhancement.
        
        This method enhances regular search with formula detection and
        cross-referencing capabilities.
        
        Args:
            query: Search query
            top_k: Number of results
            session_id: Optional session ID
            
        Returns:
            List of SearchResult (or EnhancedSearchResult if formula found)
        """
        if not self._initialized:
            self.initialize()
        
        if not self._enable_formula_enhancement:
            # Fall back to regular search
            return self.search(query, top_k, session_id)
        
        enhancer = self._get_formula_enhancer()
        enhanced_results = enhancer.search_with_formula_context(query, top_k)
        
        # Convert back to SearchResult for compatibility
        results = []
        for er in enhanced_results:
            results.append(SearchResult(
                chunk_id=er.chunk_id,
                text=er.text,
                score=er.score,
                source=er.source,
                title=er.title,
                metadata={
                    **er.metadata,
                    # Add formula-specific metadata
                    '_formulas': er.formulas,
                    '_found_via_formula': er.found_via_formula,
                    '_related_chunks': [
                        {'chunk_id': c.get('chunk_id', ''), 'text': c.get('text', '')[:100]} 
                        for c in er.related_chunks
                    ] if er.related_chunks else [],
                }
            ))
        
        return results


_rag_adapter: Optional[RAGAdapter] = None


def get_rag_adapter() -> RAGAdapter:
    """Get singleton RAG adapter instance."""
    global _rag_adapter
    if _rag_adapter is None:
        _rag_adapter = RAGAdapter()
    return _rag_adapter
