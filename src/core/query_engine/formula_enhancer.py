"""Formula-aware search enhancement module.

This module provides enhanced retrieval capabilities that leverage formula-text
associations stored in chunk metadata. It enables:

1. Formula-based retrieval: Find chunks containing specific formulas
2. Cross-reference retrieval: Given a formula, find related text chunks
3. Contextual retrieval: Enrich search results with formula context

Usage:
    enhancer = FormulaSearchEnhancer(rag_adapter)
    results = enhancer.search_with_formula_context("E=mc^2", top_k=5)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from src.observability.logger import get_logger

logger = get_logger(__name__)

# Lazy import to avoid circular dependency
if TYPE_CHECKING:
    from src.agent.adapters.rag_adapter import RAGAdapter, SearchResult


def parse_formulas_metadata(formulas_data: Any) -> List[Dict[str, Any]]:
    """Parse formulas from metadata (handles list, JSON string, or None)."""
    if not formulas_data:
        return []
    if isinstance(formulas_data, list):
        return formulas_data
    if isinstance(formulas_data, str):
        try:
            parsed = json.loads(formulas_data)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except (json.JSONDecodeError, TypeError):
            return []
    return []


# Common LaTeX math patterns for formula detection
LATEX_INLINE_PATTERN = r'\$([^$]+)\$'
LATEX_DISPLAY_PATTERN = r'\$\$([^$]+)\$\$'
# Unicode math symbols commonly used
MATH_SYMBOLS_PATTERN = r'[∫∑∏√∞≈≠≤≥±×÷∂∇∈∉⊂⊃∪∩∀∃→←↔⇒⇐⇔]'


@dataclass
class FormulaContext:
    """Represents formula context for a search result."""
    formula_latex: str
    formula_id: str
    proximity_score: float
    formula_page: Optional[int] = None
    formula_type: Optional[str] = None
    # IDs of related chunks (from formula-to-chunk mapping)
    related_chunk_ids: List[str] = field(default_factory=list)


@dataclass 
class EnhancedSearchResult:
    """Enhanced search result with formula context.
    
    Note: This is a standalone class to avoid circular imports.
    Use to_dict() method for conversion.
    """
    # Required fields matching SearchResult
    chunk_id: str = ""
    text: str = ""
    score: float = 0.0
    source: str = ""
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Formula-related information
    formulas: List[Dict[str, Any]] = field(default_factory=list)
    # Related chunks found through formula cross-reference
    related_chunks: List[Dict[str, Any]] = field(default_factory=list)
    # Whether this result was found via formula search
    found_via_formula: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "source": self.source,
            "title": self.title,
            "metadata": self.metadata,
            "formulas": self.formulas,
            "related_chunks": self.related_chunks,
            "found_via_formula": self.found_via_formula,
        }


class FormulaSearchEnhancer:
    """Enhances RAG retrieval with formula-aware search capabilities.
    
    This class bridges the gap between formula queries and text retrieval
    by:
    1. Detecting formulas in user queries
    2. Using formula metadata stored in chunks to find relevant results
    3. Cross-referencing to find related text chunks
    
    Attributes:
        rag_adapter: The RAG adapter for performing searches
        enable_formula_detection: Whether to auto-detect formulas in queries
        enable_cross_reference: Whether to find related chunks via formula mapping
    """
    
    def __init__(
        self,
        rag_adapter: Optional["RAGAdapter"] = None,
        enable_formula_detection: bool = True,
        enable_cross_reference: bool = True,
    ):
        """Initialize the formula search enhancer.
        
        Args:
            rag_adapter: Optional RAG adapter. If not provided, will be lazily initialized.
            enable_formula_detection: Auto-detect formulas in queries
            enable_cross_reference: Enable finding related chunks via formula mapping
        """
        self._rag_adapter = rag_adapter
        self.enable_formula_detection = enable_formula_detection
        self.enable_cross_reference = enable_cross_reference
        self._formula_cache: Dict[str, List[str]] = {}  # formula -> related chunk ids
    
    @property
    def rag_adapter(self) -> "RAGAdapter":
        """Lazy initialization of RAG adapter."""
        if self._rag_adapter is None:
            from src.agent.adapters.rag_adapter import get_rag_adapter
            self._rag_adapter = get_rag_adapter()
        return self._rag_adapter
    
    def detect_formulas(self, query: str) -> List[str]:
        """Detect formulas in a query string.
        
        Recognizes:
        - LaTeX inline: $E=mc^2$
        - LaTeX display: $$...$$
        - Unicode math: ∫, ∑, etc.
        - Common formula patterns: E=mc^2, F=ma, etc.
        
        Args:
            query: The search query string
            
        Returns:
            List of detected formula strings
        """
        formulas = []
        
        # Detect LaTeX inline
        inline_matches = re.findall(LATEX_INLINE_PATTERN, query)
        formulas.extend(inline_matches)
        
        # Detect LaTeX display
        display_matches = re.findall(LATEX_DISPLAY_PATTERN, query)
        formulas.extend(display_matches)
        
        # Detect Unicode math symbols
        if re.search(MATH_SYMBOLS_PATTERN, query):
            # Try to extract formula-like patterns
            # Look for patterns like "symbol expression" or "expression symbol expression"
            math_patterns = [
                r'([A-Za-z]\s*=\s*[A-Za-z0-9^_+\-*/()]+)',  # E = mc^2
                r'([A-Za-z][A-Za-z0-9]*\s*\([^)]*\))',       # f(x)
                r'(\\?[A-Za-z]+\s*[∫∑∏√∞≈≠≤≥±×÷∂∇∈∉⊂⊃∪∩∀∃→←↔⇒⇐⇔]\s*[A-Za-z0-9]+)',  # unicode math
            ]
            for pattern in math_patterns:
                matches = re.findall(pattern, query)
                formulas.extend(matches)
        
        # Deduplicate
        return list(set(formulas))
    
    def search_with_formula_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        enable_formula_search: Optional[bool] = None,
        enable_cross_ref: Optional[bool] = None,
    ) -> List[EnhancedSearchResult]:
        """Search with formula-aware context enhancement.
        
        This method combines traditional text search with formula-based retrieval:
        1. Run standard text search
        2. If query contains formulas, also search by formula
        3. Cross-reference to find related chunks
        4. Combine and rank results
        
        Args:
            query: The search query
            top_k: Number of results to return
            enable_formula_search: Override formula search setting
            enable_cross_ref: Override cross-reference setting
            
        Returns:
            List of EnhancedSearchResult with formula context
        """
        enable_formula = (
            enable_formula_search 
            if enable_formula_search is not None 
            else self.enable_formula_detection
        )
        enable_xref = (
            enable_cross_ref 
            if enable_cross_ref is not None 
            else self.enable_cross_reference
        )
        
        # Step 1: Run standard text search
        text_results = self.rag_adapter.search(query, top_k=top_k or 10)
        
        # Convert to enhanced results
        enhanced_results = [
            EnhancedSearchResult(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                source=r.source,
                title=r.title,
                metadata=r.metadata,
            )
            for r in text_results
        ]
        
        # Step 2: Extract formulas from results for context
        self._enrich_results_with_formula_context(enhanced_results)
        
        # Step 3: If query has formulas, try formula-based retrieval
        formula_results = []
        if enable_formula:
            detected_formulas = self.detect_formulas(query)
            if detected_formulas:
                logger.info(f"Detected formulas in query: {detected_formulas}")
                formula_results = self._search_by_formulas(detected_formulas, top_k=top_k or 10)
        
        # Step 4: Merge formula results into main results
        if formula_results:
            enhanced_results = self._merge_formula_results(
                enhanced_results, 
                formula_results,
                top_k=top_k or 10
            )
        
        # Step 5: Cross-reference to find related chunks
        # Always run cross-reference if results have formulas (not just when formula_results exist)
        if enable_xref and enhanced_results:
            # Check if any result has formulas
            has_formulas = any(
                bool(r.formulas) for r in enhanced_results
            )
            if has_formulas:
                enhanced_results = self._add_cross_references(enhanced_results, top_k=top_k or 10)
        
        return enhanced_results
    
    def _enrich_results_with_formula_context(
        self, 
        results: List[EnhancedSearchResult]
    ) -> None:
        """Enrich search results with formula metadata from chunk."""
        for result in results:
            metadata = result.metadata or {}
            formulas = parse_formulas_metadata(metadata.get('formulas'))
            
            if formulas:
                # Extract formula info
                formula_info = []
                for f in formulas:
                    if isinstance(f, dict):
                        formula_info.append({
                            'id': f.get('id'),
                            'latex': f.get('latex'),
                            'page': f.get('page'),
                            'type': f.get('type'),
                            'proximity_score': f.get('proximity_score'),
                        })
                result.formulas = formula_info
                
                # Build formula cache for cross-referencing
                for f in formulas:
                    formula_id = f.get('id')
                    if formula_id:
                        # Get existing list or create new one
                        chunk_ids = self._formula_cache.get(formula_id, [])
                        # Make a copy to avoid mutation issues
                        if chunk_ids:
                            chunk_ids = list(chunk_ids)
                        else:
                            chunk_ids = []
                        if result.chunk_id not in chunk_ids:
                            chunk_ids.append(result.chunk_id)
                        self._formula_cache[formula_id] = chunk_ids
    
    def _search_by_formulas(
        self, 
        formulas: List[str],
        top_k: int = 10
    ) -> List[EnhancedSearchResult]:
        """Search for chunks containing specific formulas.
        
        Args:
            formulas: List of formula strings to search for
            top_k: Number of results per formula
            
        Returns:
            List of enhanced results found via formula matching
        """
        results = []
        
        # Search by each formula - use the formula as part of query
        for formula in formulas:
            # Create a search query that includes the formula
            # This will match chunks that have this formula in their metadata
            formula_query = f"formula: {formula}"
            
            # Search using the formula text
            search_results = self.rag_adapter.search(formula_query, top_k=top_k)
            
            for r in search_results:
                # Check if this chunk actually has the formula
                metadata = r.metadata or {}
                chunk_formulas = parse_formulas_metadata(metadata.get('formulas'))
                
                # Check if any of the chunk's formulas match our search
                matched = False
                for cf in chunk_formulas:
                    if isinstance(cf, dict):
                        cf_latex = cf.get('latex', '')
                        if formula.lower() in cf_latex.lower() or cf_latex.lower() in formula.lower():
                            matched = True
                            break
                
                if matched or not chunk_formulas:
                    enhanced = EnhancedSearchResult(
                        chunk_id=r.chunk_id,
                        text=r.text,
                        score=r.score,
                        source=r.source,
                        title=r.title,
                        metadata=r.metadata,
                        found_via_formula=True,
                    )
                    self._enrich_results_with_formula_context([enhanced])
                    results.append(enhanced)
        
        return results
    
    def _merge_formula_results(
        self,
        text_results: List[EnhancedSearchResult],
        formula_results: List[EnhancedSearchResult],
        top_k: int = 10,
    ) -> List[EnhancedSearchResult]:
        """Merge formula-based results with text results using RRF.
        
        Args:
            text_results: Results from text search
            formula_results: Results from formula search
            top_k: Final number of results
            
        Returns:
            Merged and reranked results
        """
        from src.core.query_engine.fusion import RRFFusion
        
        fusion = RRFFusion(k=60)
        
        # Create a mapping of chunk_id -> result
        result_map: Dict[str, EnhancedSearchResult] = {}
        
        # Add text results with rank
        for idx, result in enumerate(text_results):
            result_map[result.chunk_id] = result
        
        # Add formula results, boosting their scores
        for idx, result in enumerate(formula_results):
            if result.chunk_id in result_map:
                # Already exists - merge formulas
                existing = result_map[result.chunk_id]
                if result.formulas:
                    existing.formulas.extend(result.formulas)
                existing.found_via_formula = existing.found_via_formula or result.found_via_formula
            else:
                result_map[result.chunk_id] = result
        
        # Apply RRF fusion
        # Build lists of (chunk_id, score) for fusion
        text_rank_list = [(r.chunk_id, r.score) for r in text_results]
        formula_rank_list = [(r.chunk_id, r.score * 1.5) for r in formula_results]  # Boost formula results
        
        # Get fused scores
        fused_scores = fusion._compute_rrf_scores(
            text_rank_list + formula_rank_list,
            top_k * 2  # Get more for filtering
        )
        
        # Rebuild results with fused scores
        final_results = []
        for chunk_id, fused_score in fused_scores[:top_k]:
            if chunk_id in result_map:
                result = result_map[chunk_id]
                result.score = fused_score
                final_results.append(result)
        
        # Sort by score
        final_results.sort(key=lambda x: x.score, reverse=True)
        
        return final_results
    
    def _add_cross_references(
        self,
        results: List[EnhancedSearchResult],
        top_k: int = 10,
    ) -> List[EnhancedSearchResult]:
        """Add related chunks via formula cross-referencing.

        For each result with formulas, find related chunks using
        the formula-to-chunk mapping stored in chunk metadata.

        Args:
            results: Current search results
            top_k: Maximum related chunks per result
            
        Returns:
            Results with related_chunks populated
        """
        for result in results:
            if not result.formulas:
                continue
            
            # Get formula IDs from this result
            related_chunk_ids: Set[str] = set()
            
            for formula in result.formulas:
                formula_id = formula.get('id')
                if formula_id:
                    # Look up related chunks from cache
                    cached = self._formula_cache.get(formula_id, [])
                    related_chunk_ids.update(cached)
            
            # Remove self from related chunks
            related_chunk_ids.discard(result.chunk_id)
            
            if not related_chunk_ids:
                continue
            
            # Fetch related chunk details from vector store
            related_chunks = self._fetch_related_chunks(
                list(related_chunk_ids), top_k
            )
            result.related_chunks = related_chunks
        
        return results
    
    def _fetch_related_chunks(
        self,
        chunk_ids: List[str],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch actual chunk content for given chunk IDs.
        
        Args:
            chunk_ids: List of chunk IDs to fetch
            top_k: Maximum number to fetch
            
        Returns:
            List of chunk data dicts
        """
        if not chunk_ids:
            return []
        
        # Try to get chunks by IDs using vector store
        try:
            # Import here to avoid circular dependency
            from src.agent.adapters.rag_adapter import RAGAdapter
            
            logger.info(f"_fetch_related_chunks called with IDs: {chunk_ids[:top_k]}")
            
            # Check if rag_adapter has get_by_ids method
            if hasattr(self.rag_adapter, 'get_by_ids'):
                chunks = self.rag_adapter.get_by_ids(chunk_ids[:top_k])
                logger.info(f"get_by_ids returned {len(chunks)} chunks")
                return [
                    {
                        "chunk_id": c.chunk_id,
                        "text": c.text,
                        "source": c.source,
                        "title": c.title,
                        "metadata": c.metadata,
                    }
                    for c in chunks
                ]
            else:
                # Fallback: use search to find these chunks
                # Search with all IDs as query (not ideal but works)
                logger.warning(
                    "RAGAdapter does not support get_by_ids, "
                    "cross-reference lookup may be incomplete"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch related chunks: {e}")
        
        # Return empty if fetch failed - IDs are still in formula metadata
        return []
    
    def get_formula_related_chunks(
        self,
        formula_latex: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get all chunks related to a specific formula.
        
        This is a direct lookup method that finds chunks containing
        or related to a specific formula.
        
        Args:
            formula_latex: The LaTeX formula string
            top_k: Number of results to return
            
        Returns:
            List of search results containing the formula (as dicts)
        """
        # First, search for chunks that might contain this formula
        search_query = formula_latex
        results = self.rag_adapter.search(search_query, top_k=top_k * 2)
        
        # Filter to only those with actual formula match
        filtered = []
        for r in results:
            metadata = r.metadata or {}
            formulas = parse_formulas_metadata(metadata.get('formulas'))
            
            for f in formulas:
                if isinstance(f, dict):
                    f_latex = f.get('latex', '')
                    if (formula_latex.lower() in f_latex.lower() or 
                        f_latex.lower() in formula_latex.lower()):
                        filtered.append({
                            "chunk_id": r.chunk_id,
                            "text": r.text,
                            "score": r.score,
                            "source": r.source,
                            "title": r.title,
                            "metadata": r.metadata,
                        })
                        break
        
        return filtered[:top_k]


# Singleton instance
_formula_enhancer: Optional["FormulaSearchEnhancer"] = None


def get_formula_enhancer(
    rag_adapter: Optional["RAGAdapter"] = None,
) -> "FormulaSearchEnhancer":
    """Get singleton formula enhancer instance."""
    global _formula_enhancer
    if _formula_enhancer is None:
        _formula_enhancer = FormulaSearchEnhancer(rag_adapter=rag_adapter)
    return _formula_enhancer
