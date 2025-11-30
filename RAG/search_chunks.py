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


def query_by_chapter(query_text, chapter, top_k=5, namespace=""):
    """Query within a specific chapter"""
    return query_pinecone(
        query_text, 
        top_k=top_k, 
        namespace=namespace,
        filter_dict={"chapter": {"$eq": chapter}}
    )


def query_by_section_type(query_text, section_type, top_k=5, namespace=""):
    """Query within a specific section type (regulation, schedule, toc, preamble)"""
    return query_pinecone(
        query_text, 
        top_k=top_k, 
        namespace=namespace,
        filter_dict={"section_type": {"$eq": section_type}}
    )


def query_regulations_only(query_text, top_k=5, namespace=""):
    """Query only regulation chunks (excludes schedules, toc, preamble)"""
    return query_by_section_type(query_text, "regulation", top_k, namespace)


def query_pinecone_by_id(chunk_id, namespace=""):
    """Retrieve a specific chunk by its ID"""
    result = index.fetch(ids=[chunk_id], namespace=namespace)
    return result.vectors.get(chunk_id)


def get_definitions_chunk(namespace=""):
    """Get the definitions chunk (Regulation 2) - useful for context"""
    result = index.fetch(ids=["chunk_003_chI_reg2"], namespace=namespace)
    return result.vectors.get("chunk_003_chI_reg2")


def display_results(query_text, matches):
    """Display search results with new metadata structure"""
    print(f"\nQuery: {query_text}")
    print(f"Found {len(matches)} matches\n")
    
    for i, match in enumerate(matches, 1):
        metadata = match['metadata']
        
        # Build location string
        location_parts = []
        if metadata.get('chapter'):
            location_parts.append(f"Ch.{metadata['chapter']}")
        if metadata.get('regulation'):
            location_parts.append(f"Reg.{metadata['regulation']}")
        if metadata.get('schedule_name'):
            location_parts.append(metadata['schedule_name'])
        location = " | ".join(location_parts) if location_parts else metadata.get('section_type', 'N/A')
        
        print(f"#{i} | Score: {match['score']:.4f} | {location}")
        print(f"Section Type: {metadata.get('section_type', 'N/A')}")
        
        if metadata.get('chapter_title'):
            print(f"Chapter: {metadata['chapter_title']}")
        
        if metadata.get('has_amendments'):
            print(f"Has Amendments: Yes")
        
        print(f"\nContent:\n{metadata.get('text', 'No text')[:500]}...")
        print("-" * 80 + "\n")


def save_results(query_text, matches, filename=None):
    """Save results to JSON file"""
    if not filename:
        filename = f"query_{query_text[:30].replace(' ', '_')}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump([{
            'score': m['score'],
            'id': m['id'],
            'metadata': m['metadata']
        } for m in matches], f, indent=2, ensure_ascii=False)
    print(f"Saved to {filename}")


def get_context_for_agent(query_text, top_k=3, include_definitions=True, namespace=""):
    """
    Get context chunks formatted for AI agent consumption.
    Optionally includes definitions chunk for term resolution.
    """
    matches = query_pinecone(query_text, top_k=top_k, namespace=namespace)
    
    context_chunks = []
    
    # Optionally add definitions for context
    if include_definitions:
        definitions = get_definitions_chunk(namespace)
        if definitions:
            context_chunks.append({
                'id': 'chunk_003_chI_reg2',
                'type': 'definitions',
                'content': definitions['metadata'].get('text', '')
            })
    
    # Add matched chunks
    for match in matches:
        metadata = match['metadata']
        context_chunks.append({
            'id': match['id'],
            'score': match['score'],
            'type': metadata.get('section_type', ''),
            'chapter': metadata.get('chapter', ''),
            'regulation': metadata.get('regulation', ''),
            'content': metadata.get('text', '')
        })
    
    return context_chunks


def main():
    print("=" * 60)
    print("SEBI CUSTODIAN REGULATIONS - SEARCH TOOL")
    print("=" * 60)
    print("\nCommands:")
    print("  exit/quit  - Exit the tool")
    print("  stats      - Show index statistics")
    print("  filter:ch  - Filter by chapter (e.g., filter:II)")
    print("  filter:reg - Filter regulations only")
    print("\n")
    
    while True:
        query_text = input("Query: ").strip()
        
        if not query_text:
            continue
            
        if query_text.lower() in ['exit', 'quit']:
            break
        
        if query_text.lower() == 'stats':
            stats = index.describe_index_stats()
            print(f"\nIndex Stats:")
            print(f"  Total vectors: {stats.total_vector_count}")
            print(f"  Dimension: {stats.dimension}")
            print(f"  Namespaces: {stats.namespaces}\n")
            continue
        
        try:
            # Parse filter commands
            filter_chapter = None
            regulations_only = False
            
            if query_text.startswith('filter:ch:'):
                parts = query_text.split(':', 2)
                filter_chapter = parts[2].split()[0]
                query_text = ' '.join(parts[2].split()[1:])
            elif query_text.startswith('filter:reg:'):
                regulations_only = True
                query_text = query_text.replace('filter:reg:', '').strip()
            
            top_k = int(input("Results (default 5): ").strip() or 5)
            
            # Execute query with appropriate filter
            if filter_chapter:
                print(f"Filtering by Chapter {filter_chapter}")
                matches = query_by_chapter(query_text, filter_chapter, top_k=top_k)
            elif regulations_only:
                print("Filtering regulations only")
                matches = query_regulations_only(query_text, top_k=top_k)
            else:
                matches = query_pinecone(query_text, top_k=top_k)
            
            display_results(query_text, matches)
            
            if input("Save? (y/n): ").strip().lower() == 'y':
                save_results(query_text, matches)
            
            print()
            
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
