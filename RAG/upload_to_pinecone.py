import os
import json
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

from pinecone import Pinecone

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Connect to the index
index = pc.Index("onfinanceai")


def delete_all_vectors(namespace=""):
    """Delete all vectors from the index"""
    print("Fetching current index stats...")
    stats = index.describe_index_stats()
    print(f"Current total vectors: {stats.total_vector_count}")
    
    if stats.total_vector_count == 0:
        print("Index is already empty.")
        return
    
    print(f"\nDeleting all vectors from namespace: '{namespace or 'default'}'...")
    
    # Delete all vectors in the namespace
    index.delete(delete_all=True, namespace=namespace)
    
    print("Deletion complete. Verifying...")
    
    # Verify deletion
    stats = index.describe_index_stats()
    print(f"Vectors after deletion: {stats.total_vector_count}")


def load_chunks(file_path):
    """Load chunk data from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} chunks from {file_path}")
    return data


def prepare_records_from_chunks(chunks):
    """Prepare records for Pinecone upsert from new chunk format"""
    records = []
    print("Preparing records for upsert...")
    
    for chunk in tqdm(chunks, desc="Creating records"):
        # Build metadata from chunk structure
        metadata = {
            'text': chunk.get('content', ''),
            'chapter': chunk.get('chapter') or '',
            'chapter_title': chunk.get('chapter_title') or '',
            'regulation': chunk.get('regulation') or '',
            'regulation_title': chunk.get('regulation_title') or '',
            'section_type': chunk.get('section_type', ''),
            'schedule_name': chunk.get('schedule_name') or '',
            'token_estimate': chunk.get('token_estimate', 0),
            'has_amendments': chunk.get('has_amendments', False),
            'amendment_refs': ','.join(chunk.get('amendment_refs', [])),
            'doc_type': 'SEBI Custodian Regulations 1996',
            'filename': '1758886606773.pdf'
        }
        
        record = {
            'id': chunk.get('chunk_id', ''),
            'metadata': metadata
        }
        
        records.append(record)
    
    return records


def upload_to_pinecone(records, namespace="", batch_size=50):
    """Upload using Pinecone Inference API with text-to-embedding"""
    print(f"\nUploading {len(records)} records to Pinecone using Inference API...")
    print(f"Embedding model: llama-text-embed-v2")
    
    successful = 0
    failed = 0
    
    for i in tqdm(range(0, len(records), batch_size), desc="Uploading batches"):
        batch = records[i:i + batch_size]
        
        try:
            # Generate embeddings from text content
        texts = [r['metadata']['text'] for r in batch]
        embeddings = pc.inference.embed(
            model="llama-text-embed-v2",
            inputs=texts,
            parameters={"input_type": "passage", "truncate": "END"}
        )
        
        # Prepare vectors with embeddings
        vectors = []
        for j, record in enumerate(batch):
            vectors.append({
                'id': record['id'],
                'values': embeddings[j]['values'],
                'metadata': record['metadata']
            })
        
        # Upsert the vectors
        index.upsert(vectors=vectors, namespace=namespace)
            successful += len(batch)
            
        except Exception as e:
            print(f"\nError uploading batch {i//batch_size + 1}: {e}")
            failed += len(batch)
    
    print(f"\nUpload complete! Successful: {successful}, Failed: {failed}")


def main():
    import sys
    
    # Default chunk file path
    chunk_file = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'data', 
        '1758886606773_chunks.json'
    )
    
    # Allow override via command line
    if len(sys.argv) > 1:
        chunk_file = sys.argv[1]
    
    print("=" * 60)
    print("PINECONE DATA UPLOAD")
    print("=" * 60)
    
    # Step 1: Delete existing data
    print("\n[STEP 1] Deleting existing vectors...")
    delete_all_vectors()
    
    # Step 2: Load new chunks
    print("\n[STEP 2] Loading chunk data...")
    chunks = load_chunks(chunk_file)
    
    # Step 3: Show sample
    print("\n" + "=" * 60)
    print("SAMPLE CHUNK STRUCTURE:")
    print("=" * 60)
    sample = chunks[0]
    print(f"Chunk ID: {sample.get('chunk_id')}")
    print(f"Section Type: {sample.get('section_type')}")
    print(f"Chapter: {sample.get('chapter')}")
    print(f"Regulation: {sample.get('regulation')}")
    print(f"Token Estimate: {sample.get('token_estimate')}")
    print(f"Content preview: {sample.get('content', '')[:150]}...")
    print("=" * 60)
    
    # Step 4: Prepare records
    print("\n[STEP 3] Preparing records...")
    records = prepare_records_from_chunks(chunks)
    
    # Step 5: Upload
    print("\n[STEP 4] Uploading to Pinecone...")
    upload_to_pinecone(records)
    
    # Step 6: Verify
    print("\n[STEP 5] Verifying upload...")
    stats = index.describe_index_stats()
    print(f"\nIndex stats after upload:")
    print(f"  Total vectors: {stats.total_vector_count}")
    print(f"  Dimension: {stats.dimension}")
    print(f"  Index fullness: {stats.index_fullness}")
    print(f"  Namespaces: {stats.namespaces}")
    
    print("\n" + "=" * 60)
    print("UPLOAD COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
