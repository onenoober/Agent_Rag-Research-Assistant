"""Formula Extractor transform for extracting mathematical formulas from PDFs.

This transform uses Pix2Text to detect and recognize mathematical formulas (LaTeX)
from PDF documents, enriching chunks with formula metadata.

Enhanced Features:
- Position-based formula-text association using proximity
- Formula-to-chunk cross-referencing via unique IDs
- Context extraction (nearby text) for better retrieval
"""

import hashlib
import re
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from src.core.settings import Settings
from src.core.types import Chunk
from src.core.trace.trace_context import TraceContext
from src.ingestion.transform.base_transform import BaseTransform
from src.observability.logger import get_logger

logger = get_logger(__name__)

DEFAULT_FORMULA_DEVICE = "cpu"
DEFAULT_FORMULA_LANGUAGE = "en"

# Position proximity threshold (in PDF coordinates) for associating
# formula with nearby text blocks
DEFAULT_PROXIMITY_THRESHOLD = 50.0


class FormulaExtractor(BaseTransform):
    """Extracts mathematical formulas from PDF documents using Pix2Text.
    
    Enhanced Features:
    - Position-based formula-text association using proximity
    - Formula-to-chunk cross-referencing via unique IDs
    - Context extraction (nearby text) for better retrieval
    """
    
    def __init__(
        self, 
        settings: Settings,
        device: str = DEFAULT_FORMULA_DEVICE,
        language: str = DEFAULT_FORMULA_LANGUAGE,
        proximity_threshold: float = DEFAULT_PROXIMITY_THRESHOLD,
    ):
        self.settings = settings
        self.device = device
        self.language = language
        self.proximity_threshold = proximity_threshold
        self._pix2text = None
        
        self._formula_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()
        
        self._init_pix2text()
    
    def _init_pix2text(self) -> None:
        """Initialize Pix2Text engine."""
        try:
            from pix2text import Pix2Text
            
            formula_config = getattr(self.settings, 'formula_extraction', None)
            if formula_config and not getattr(formula_config, 'enabled', True):
                logger.info("Formula extraction is disabled in settings")
                return
            
            self._pix2text = Pix2Text.from_config(
                enable_formula=True,
                enable_table=False,
                language=self.language,
                device=self.device
            )
            logger.info(f"FormulaExtractor initialized (device={self.device}, language={self.language})")
            
        except ImportError as e:
            logger.warning(f"Pix2Text not installed: {e}. Formula extraction will be skipped.")
            self._pix2text = None
        except Exception as e:
            logger.warning(f"Failed to initialize Pix2Text: {e}. Formula extraction will be skipped.")
            self._pix2text = None
    
    def _extract_formulas_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract all formulas from a PDF file."""
        if not self._pix2text:
            return []
        
        with self._cache_lock:
            if pdf_path in self._formula_cache:
                logger.debug(f"Formula cache hit for {pdf_path}")
                return self._formula_cache[pdf_path]
        
        formulas = []
        
        try:
            logger.info(f"Extracting formulas from PDF: {pdf_path}")
            
            result = self._pix2text.recognize_pdf(pdf_path)
            
            # Handle different return types: Document, Page, list
            pages = []
            if result is None:
                pages = []
            elif hasattr(result, 'pages'):
                # Document object
                pages = result.pages
            elif hasattr(result, 'elements'):
                # Single Page object
                pages = [result]
            elif isinstance(result, list):
                pages = result
            elif hasattr(result, '__iter__'):
                pages = list(result)
            else:
                logger.warning(f"Unexpected result type from recognize_pdf: {type(result)}")
                return []
            
            for page_idx, page in enumerate(pages):
                if not hasattr(page, 'elements'):
                    continue
                    
                for elem in page.elements:
                    if not hasattr(elem, 'meta') or not elem.meta:
                        continue
                    
                    meta = elem.meta
                    
                    # Handle meta - could be a dict or list
                    # Case 1: meta is a dict - this is usually a formula (isolated)
                    if isinstance(meta, dict):
                        formula_text = meta.get('text', '')
                        if formula_text:
                            # This is likely a formula
                            position = None
                            pos_array = meta.get('position')
                            if pos_array is not None and len(pos_array) >= 4:
                                position = [
                                    float(pos_array[0][0]),
                                    float(pos_array[0][1]),
                                    float(pos_array[2][0]),
                                    float(pos_array[2][1]),
                                ]
                            
                            # Determine type: check if it's explicitly set, default to 'isolated'
                            formula_type = meta.get('type', 'isolated')
                            # If type is not explicitly isolated/inline but has text, treat as isolated
                            if formula_type not in ('isolated', 'inline'):
                                formula_type = 'isolated'
                            
                            formulas.append({
                                'latex': formula_text,
                                'page': page_idx,
                                'position': position,
                                'type': formula_type,
                                'score': meta.get('score', 0.0),
                            })
                    
                    # Case 2: meta is a list - iterate through items
                    elif isinstance(meta, list):
                        for item in meta:
                            if not isinstance(item, dict):
                                continue
                            # Look for isolated or inline formulas
                            if item.get('type') in ('isolated', 'inline'):
                                formula_text = item.get('text', '')
                                if formula_text:
                                    position = None
                                    pos_array = item.get('position')
                                    if pos_array is not None and len(pos_array) >= 4:
                                        position = [
                                            float(pos_array[0][0]),
                                            float(pos_array[0][1]),
                                            float(pos_array[2][0]),
                                            float(pos_array[2][1]),
                                        ]
                                    
                                    formulas.append({
                                        'latex': formula_text,
                                        'page': page_idx,
                                        'position': position,
                                        'type': item.get('type', 'isolated'),
                                        'score': item.get('score', 0.0),
                                    })
            
            logger.info(f"Extracted {len(formulas)} formulas from {pdf_path}")
            
            with self._cache_lock:
                self._formula_cache[pdf_path] = formulas
            
            return formulas
            
        except Exception as e:
            logger.error(f"Failed to extract formulas from {pdf_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _get_page_number(self, chunk: Chunk) -> Optional[int]:
        """Extract page number from chunk metadata."""
        # Try different metadata keys
        page = chunk.metadata.get('page')
        if page is not None:
            return int(page) - 1 if isinstance(page, int) and page > 0 else int(page)
        
        # Try page_num (used by document_chunker)
        page_num = chunk.metadata.get('page_num')
        if page_num is not None:
            return int(page_num) - 1 if isinstance(page_num, int) and page_num > 0 else int(page_num)
        
        # Try to extract from source_path pattern
        source_path = chunk.metadata.get('source_path', '')
        page_match = re.search(r'[_-]page[_-]?(\d+)|\[(\d+)\]', source_path, re.IGNORECASE)
        if page_match:
            page_num = int(page_match.group(1) or page_match.group(2))
            return page_num - 1
        
        return None
    
    def _generate_formula_id(self, pdf_path: str, formula: Dict[str, Any], index: int) -> str:
        """Generate a unique ID for a formula.
        
        Args:
            pdf_path: Source PDF file path
            formula: Formula data dict
            index: Index of formula in the document
        
        Returns:
            Unique formula ID string
        """
        formula_text = formula.get('latex', '')
        page = formula.get('page', 0)
        # Generate hash from formula text + page + index
        id_str = f"{pdf_path}_{page}_{index}_{formula_text[:50]}"
        formula_hash = hashlib.md5(id_str.encode('utf-8')).hexdigest()[:12]
        return f"formula_{formula_hash}"
    
    def _calculate_position_distance(
        self, 
        pos1: Optional[List[float]], 
        pos2: Optional[List[float]]
    ) -> float:
        """Calculate vertical distance between two positions (PDF coordinates).
        
        Args:
            pos1: [x1, y1, x2, y2] position
            pos2: [x1, y1, x2, y2] position
        
        Returns:
            Vertical distance between centers, or infinity if positions invalid
        """
        if not pos1 or not pos2 or len(pos1) < 4 or len(pos2) < 4:
            return float('inf')
        
        # Calculate center Y coordinates (PDF y-axis is typically bottom-to-top)
        center_y1 = (pos1[1] + pos1[3]) / 2
        center_y2 = (pos2[1] + pos2[3]) / 2
        
        return abs(center_y1 - center_y2)
    
    def _estimate_chunk_position(
        self, 
        chunk: Chunk, 
        page_formulas: List[Dict[str, Any]],
        page_idx: int
    ) -> Optional[List[float]]:
        """Estimate chunk position on page based on its text and nearby formulas.
        
        This is a heuristic approach - we use formula positions as anchors
        and estimate chunk position based on its chunk_index relative to formulas.
        
        Args:
            chunk: The chunk to estimate position for
            page_formulas: Formulas on the same page
            page_idx: Page index (0-based)
        
        Returns:
            Estimated position [x1, y1, x2, y2] or None
        """
        if not page_formulas:
            return None
        
        # Get chunk's approximate vertical position based on chunk_index
        # This is a rough heuristic - assumes roughly equal distribution
        chunk_index = chunk.metadata.get('chunk_index', 0)
        total_chunks = chunk.metadata.get('_total_chunks_on_page', 1)
        
        # Estimate position as proportional to chunk index
        # PDF pages typically have y in range [0, 842] for letter size
        page_height = 842.0  # Standard letter size
        y_ratio = min(chunk_index / max(total_chunks - 1, 1), 1.0)
        estimated_y = page_height * (1 - y_ratio)  # Invert since PDF y is bottom-up
        
        return [50, estimated_y - 50, 550, estimated_y + 50]
    
    def _associate_formulas_with_chunk(
        self, 
        chunk: Chunk, 
        formulas: List[Dict[str, Any]],
        page_num: Optional[int] = None,
        all_chunks: Optional[List[Chunk]] = None
    ) -> List[Dict[str, Any]]:
        """Associate formulas with a chunk based on page number and position proximity.
        
        Enhanced association strategy:
        1. If page_num available, only match formulas on that page
        2. If position info available, use proximity for better matching
        3. Add unique formula IDs and context for cross-referencing
        
        Args:
            chunk: Target chunk
            formulas: All formulas from the source PDF
            page_num: Page number of the chunk (0-based)
            all_chunks: All chunks from the document (for position estimation)
        
        Returns:
            List of associated formula dicts with enhanced metadata
        """
        # Filter by page first
        if page_num is not None:
            page_formulas = [f for f in formulas if f.get('page') == page_num]
        else:
            page_formulas = formulas
        
        if not page_formulas:
            return []
        
        # Enhance formulas with unique IDs
        result = []
        pdf_path = chunk.metadata.get('source_path', '')
        
        # Estimate total chunks on this page for position heuristics
        if all_chunks and page_num is not None:
            page_chunks = [c for c in all_chunks if self._get_page_number(c) == page_num]
            total_on_page = len(page_chunks)
        else:
            total_on_page = 1
        
        for idx, formula in enumerate(page_formulas):
            # Generate unique formula ID
            formula_id = self._generate_formula_id(pdf_path, formula, idx)
            
            # Estimate chunk position for proximity calculation
            chunk_pos = self._estimate_chunk_position(chunk, page_formulas, page_num)
            formula_pos = formula.get('position')
            
            # Calculate proximity score
            distance = self._calculate_position_distance(chunk_pos, formula_pos)
            proximity_score = max(0, 1 - distance / self.proximity_threshold) if distance != float('inf') else 0.5
            
            # Build enhanced formula record
            enhanced_formula = {
                'id': formula_id,
                'latex': formula.get('latex'),
                'page': formula.get('page'),
                'position': formula.get('position'),
                'type': formula.get('type', 'isolated'),
                'score': formula.get('score', 0.0),
                # Enhanced fields for retrieval
                'proximity_score': proximity_score,
                'associated_chunk_id': chunk.id,
            }
            
            result.append(enhanced_formula)
        
        # Sort by proximity score (higher is better match)
        result.sort(key=lambda x: x.get('proximity_score', 0), reverse=True)
        
        return result
    
    def transform(
        self,
        chunks: List[Chunk],
        trace: Optional[TraceContext] = None
    ) -> List[Chunk]:
        """Extract formulas from PDF and associate with chunks."""
        if not self._pix2text:
            logger.debug("Pix2Text not available, skipping formula extraction")
            return chunks
        
        if not chunks:
            return chunks
        
        pdf_paths = set()
        for chunk in chunks:
            source_path = chunk.metadata.get('source_path', '')
            if source_path and source_path.lower().endswith('.pdf'):
                pdf_paths.add(source_path)
        
        if not pdf_paths:
            logger.debug("No PDF files found in chunks, skipping formula extraction")
            return chunks
        
        all_formulas: Dict[str, List[Dict[str, Any]]] = {}
        for pdf_path in pdf_paths:
            formulas = self._extract_formulas_from_pdf(pdf_path)
            all_formulas[pdf_path] = formulas
        
        chunks_with_formulas = 0
        
        # Build formula-to-chunk mapping for cross-referencing
        # This maps formula IDs to the chunks they are associated with
        formula_chunk_mapping: Dict[str, List[str]] = {}
        
        for chunk in chunks:
            source_path = chunk.metadata.get('source_path', '')
            if source_path not in all_formulas:
                continue
            
            page_num = self._get_page_number(chunk)
            formulas = all_formulas[source_path]
            chunk_formulas = self._associate_formulas_with_chunk(
                chunk, formulas, page_num, chunks
            )
            
            if chunk_formulas:
                # Store formula IDs list for easier lookup
                formula_ids_list = [f.get('id') for f in chunk_formulas if f.get('id')]
                chunk.metadata['formula_ids'] = formula_ids_list
                chunk.metadata['formulas'] = chunk_formulas
                chunk.metadata['formulas_extracted'] = True
                chunks_with_formulas += 1
                
                # Build mapping: formula_id -> list of chunk_ids
                for formula in chunk_formulas:
                    formula_id = formula.get('id')
                    if formula_id:
                        if formula_id not in formula_chunk_mapping:
                            formula_chunk_mapping[formula_id] = []
                        if chunk.id not in formula_chunk_mapping[formula_id]:
                            formula_chunk_mapping[formula_id].append(chunk.id)
                
                logger.debug(
                    f"Added {len(chunk_formulas)} formulas to chunk {chunk.id} "
                    f"(page {page_num})"
                )
        
        # Store formula-to-chunk mapping in first chunk's metadata for retrieval
        # This allows finding all chunks related to a formula
        if formula_chunk_mapping:
            for chunk in chunks:
                if chunk.metadata.get('formulas_extracted'):
                    chunk.metadata['_formula_chunk_mapping'] = formula_chunk_mapping
                    break
        
        logger.info(
            f"Formula extraction complete: {chunks_with_formulas}/{len(chunks)} "
            f"chunks have formulas"
        )
        
        if trace is not None:
            trace.record_stage("formula_extraction", {
                "pdf_count": len(pdf_paths),
                "total_formulas": sum(len(f) for f in all_formulas.values()),
                "chunks_with_formulas": chunks_with_formulas,
            })
        
        return chunks
