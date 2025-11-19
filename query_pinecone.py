import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("onfinanceai")

def query_pinecone(query_text, top_k=5, namespace=""):
    """Query Pinecone and retrieve matching chunks"""
    print(f"\n{'='*80}")
    print(f"QUERY: {query_text}")
    print(f"{'='*80}\n")
    
    # Generate query embedding using the same model as the index
    query_embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[query_text],
        parameters={"input_type": "query", "truncate": "END"}
    )
    
    # Query the index
    results = index.query(
        vector=query_embedding[0]['values'],
        top_k=top_k,
        include_metadata=True,
        namespace=namespace
    )
    
    # Display results
    print(f"Found {len(results['matches'])} matches:\n")
    
    retrieved_chunks = []
    for i, match in enumerate(results['matches'], 1):
        chunk_data = {
            'rank': i,
            'score': match['score'],
            'id': match['id'],
            'metadata': match['metadata']
        }
        retrieved_chunks.append(chunk_data)
        
        print(f"{'─'*80}")
        print(f"RANK #{i} | Similarity Score: {match['score']:.4f}")
        print(f"ID: {match['id']}")
        print(f"File: {match['metadata'].get('filename', 'N/A')}")
        print(f"Page: {match['metadata'].get('page_number', 'N/A')}")
        print(f"Type: {match['metadata'].get('type', 'N/A')}")
        print(f"\nTEXT CONTENT:")
        print(f"{match['metadata'].get('text', 'No text found')}")
        print(f"{'─'*80}\n")
    
    return retrieved_chunks

def main():
    print("\n" + "="*80)
    print("PINECONE QUERY TOOL")
    print("="*80)
    print("\nThis tool allows you to search your Pinecone index and retrieve matching chunks.")
    print("Enter your queries below. Type 'exit' or 'quit' to stop.\n")
    
    while True:
        query_text = input("Enter your query: ").strip()
        
        if query_text.lower() in ['exit', 'quit', '']:
            print("\nExiting query tool. Goodbye!")
            break
        
        try:
            # Ask for number of results
            top_k_input = input("How many results do you want? (default: 5): ").strip()
            top_k = int(top_k_input) if top_k_input else 5
            
            # Query Pinecone
            results = query_pinecone(query_text, top_k=top_k)
            
            # Option to save results
            save = input("\nWould you like to save these results? (y/n): ").strip().lower()
            if save == 'y':
                import json
                filename = f"query_results_{query_text[:30].replace(' ', '_')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {filename}")
            
            print("\n" + "="*80 + "\n")
            
        except Exception as e:
            print(f"\nError: {e}\n")
            continue

if __name__ == "__main__":
    main()

