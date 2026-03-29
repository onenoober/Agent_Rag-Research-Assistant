"""List all chunks with proper encoding - output to file."""
import sys
sys.path.insert(0, '.')

from src.core.settings import load_settings
from src.libs.vector_store.vector_store_factory import VectorStoreFactory

settings = load_settings()
vs = VectorStoreFactory.create(settings)

# Get all documents
collection = vs.client.get_collection('default')
docs = collection.get()

output_lines = []
output_lines.append(f"Total chunks: {len(docs['ids'])}")
output_lines.append("")

# Show all chunks with their content
for i, chunk_id in enumerate(docs['ids']):
    output_lines.append("=" * 70)
    output_lines.append(f"[{i+1}] Chunk ID: {chunk_id}")
    if 'documents' in docs:
        text = docs['documents'][i]
        if text:
            output_lines.append(f"Text:\n{text}")
        else:
            output_lines.append("Text: (empty)")
    output_lines.append("")

# Write to file with UTF-8 encoding
with open('chunks_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

print("Output written to chunks_output.txt")
