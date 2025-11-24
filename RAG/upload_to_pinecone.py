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

def load_json_data(file_path):
    """Load JSON data from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} chunks from {file_path}")
    return data

def prepare_records(data):
    """Prepare records for Pinecone upsert with text (for inference API)"""
    records = []
    print("Preparing records for upsert...")
    
    for chunk in tqdm(data, desc="Creating records"):
        metadata = chunk.get('metadata', {})
        
        # For Inference API, include 'text' in metadata
        record = {
            'id': chunk.get('element_id', ''),
            'metadata': {
                'text': chunk.get('text', ''),
                'type': chunk.get('type', ''),
                'filename': metadata.get('filename', ''),
                'page_number': metadata.get('page_number', 0),
                'filetype': metadata.get('filetype', ''),
                'languages': str(metadata.get('languages', [])),
            }
        }
        
        entities = metadata.get('entities', {})
        if entities:
            record['metadata']['entities'] = str(entities.get('items', []))[:1000]
            record['metadata']['relationships'] = str(entities.get('relationships', []))[:1000]
        
        records.append(record)
    
    return records

def upload_to_pinecone_with_inference(records, namespace="", batch_size=100):
    """Upload using Pinecone Inference API with text-to-embedding"""
    print(f"\nUploading {len(records)} records to Pinecone using Inference API...")
    print(f"Pinecone will generate embeddings using llama-text-embed-v2")
    
    for i in tqdm(range(0, len(records), batch_size), desc="Uploading batches"):
        batch = records[i:i + batch_size]
        
        # Use the embed method to generate embeddings from text
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
    
    print("\nUpload complete!")

def main():
    data = load_json_data('final_chunk.json')
    
    print("\n" + "="*80)
    print("SAMPLE DATA STRUCTURE:")
    print("="*80)
    print(f"Total chunks: {len(data)}")
    print(f"\nFirst chunk ID: {data[0].get('element_id')}")
    print(f"Text length: {len(data[0].get('text'))} characters")
    print(f"Text preview: {data[0].get('text', '')[:200]}...")
    print("="*80)
    
    records = prepare_records(data)
    
    print("\n" + "="*80)
    print("SAMPLE RECORD STRUCTURE:")
    print("="*80)
    print(f"Record ID: {records[0]['id']}")
    print(f"Metadata keys: {list(records[0]['metadata'].keys())}")
    print(f"Text preview in metadata: {records[0]['metadata']['text'][:200]}...")
    print("="*80)
    print("\nNote: Using Pinecone Inference API with llama-text-embed-v2")
    print("="*80)
    
    upload_to_pinecone_with_inference(records)
    
    print("\nFetching index stats...")
    stats = index.describe_index_stats()
    print(f"\nIndex stats after upload:")
    print(f"Total vectors: {stats.total_vector_count}")
    print(f"Dimension: {stats.dimension}")
    print(f"Index fullness: {stats.index_fullness}")
    print(f"Namespaces: {stats.namespaces}")

if __name__ == "__main__":
    main()
