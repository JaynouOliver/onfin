import os
import json
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("onfinanceai")

def query_pinecone(query_text, top_k=5, namespace="", filter_dict=None):
    """Query Pinecone and retrieve matching chunks"""
    query_embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[query_text],
        parameters={"input_type": "query", "truncate": "END"}
    )
    
    results = index.query(
        vector=query_embedding[0]['values'],
        top_k=top_k,
        include_metadata=True,
        namespace=namespace,
        filter=filter_dict
    )
    
    return results['matches']

def query_pinecone_by_id(chunk_id, namespace=""):
    """Retrieve a specific chunk by its ID (useful for direct references)"""
    result = index.fetch(ids=[chunk_id], namespace=namespace)
    return result.vectors.get(chunk_id)

def display_results(query_text, matches):
    """Display search results"""
    print(f"\nQuery: {query_text}")
    print(f"Found {len(matches)} matches\n")
    
    for i, match in enumerate(matches, 1):
        metadata = match['metadata']
        print(f"#{i} | Score: {match['score']:.4f} | {metadata.get('filename', 'N/A')} (p.{metadata.get('page_number', 'N/A')})")
        print(f"Prefix: {metadata.get('prefix', 'No prefix')}\n")
        print(f"Full Text:\n{metadata.get('text', 'No text')}\n")
        print("-" * 80 + "\n")

def save_results(query_text, matches):
    """Save results to JSON file"""
    filename = f"query_{query_text[:30].replace(' ', '_')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump([{
            'score': m['score'],
            'id': m['id'],
            'metadata': m['metadata']
        } for m in matches], f, indent=2, ensure_ascii=False)
    print(f"Saved to {filename}")

def main():
    print("Pinecone Query Tool - Type 'exit' to quit\n")
    
    while True:
        query_text = input("Query: ").strip()
        if not query_text or query_text.lower() in ['exit', 'quit']:
            break
        
        try:
            top_k = int(input("Results (default 5): ").strip() or 5)
            matches = query_pinecone(query_text, top_k=top_k)
            display_results(query_text, matches)
            
            if input("Save? (y/n): ").strip().lower() == 'y':
                save_results(query_text, matches)
            
            print()
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()
