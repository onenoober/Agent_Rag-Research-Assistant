"""Test script for document ingestion pipeline.

Usage:
    conda activate bigmodel
    python scripts/test_ingestion.py
"""

import sys
sys.path.insert(0, 'D:/Agent-Rag/MODULAR-RAG-MCP-SERVER')

from pathlib import Path
from src.core.settings import load_settings
from src.ingestion.pipeline import IngestionPipeline

def main():
    # Use PDF test document
    test_doc = Path("D:/Agent-Rag/MODULAR-RAG-MCP-SERVER/tests/fixtures/sample_documents/simple.pdf")
    
    # Fallback to blogger_intro if simple.pdf doesn't exist
    if not test_doc.exists():
        test_doc = Path("D:/Agent-Rag/MODULAR-RAG-MCP-SERVER/tests/fixtures/sample_documents/blogger_intro.pdf")
    
    if not test_doc.exists():
        print(f"Error: No test PDF found")
        print(f"  - Checked: {test_doc}")
        return
    
    print(f"Testing ingestion with: {test_doc}")
    print("=" * 60)
    
    # Load settings
    settings = load_settings()
    print(f"Settings loaded:")
    print(f"  - LLM provider: {settings.llm.provider}")
    print(f"  - Embedding provider: {settings.embedding.provider}")
    print(f"  - Embedding model: {settings.embedding.model}")
    print(f"  - Chunk size: {settings.ingestion.chunk_size}")
    print(f"  - Batch size: {settings.ingestion.batch_size}")
    print()
    
    # Create pipeline
    pipeline = IngestionPipeline(settings, collection="test_collection", force=True)
    
    try:
        # Run pipeline
        result = pipeline.run(str(test_doc))
        
        print("=" * 60)
        print("Ingestion Result:")
        print(f"  - Success: {result.success}")
        print(f"  - File: {result.file_path}")
        print(f"  - Doc ID: {result.doc_id}")
        print(f"  - Chunk count: {result.chunk_count}")
        print(f"  - Image count: {result.image_count}")
        print(f"  - Vector IDs: {len(result.vector_ids)}")
        
        if result.error:
            print(f"  - Error: {result.error}")
        
        if result.success:
            print("\n✅ Document ingested successfully!")
        else:
            print("\n❌ Document ingestion failed!")
            
    except Exception as e:
        print(f"\n❌ Exception during ingestion: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline.close()

if __name__ == "__main__":
    main()
