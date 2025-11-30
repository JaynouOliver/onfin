"""
Batch Processor for Compliance Generation

Processes all chunks from the PDF through the agent graph
and generates compliance items for HDFC AMC and Navi AMC.
"""

import os
import sys
import json
from datetime import datetime
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent1 import process_clause


def load_chunks(chunks_file: str) -> list:
    """Load chunks from JSON file"""
    with open(chunks_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_all_chunks(chunks: list, org_name: str, skip_toc: bool = True) -> dict:
    """
    Process all chunks through the agent for a specific organization
    
    Args:
        chunks: List of chunk dictionaries
        org_name: Organization name ("HDFC AMC" or "Navi AMC")
        skip_toc: Skip table of contents and preamble
    
    Returns:
        dict with all results and summary
    """
    results = []
    total_actionables = 0
    applicable_chunks = 0
    skipped_chunks = 0
    
    print(f"\n{'='*60}")
    print(f"Processing for: {org_name}")
    print(f"{'='*60}")
    
    for chunk in tqdm(chunks, desc=f"Processing {org_name}"):
        chunk_id = chunk.get('chunk_id', '')
        section_type = chunk.get('section_type', '')
        content = chunk.get('content', '')
        
        # Skip TOC and preamble
        if skip_toc and section_type in ['toc', 'preamble']:
            skipped_chunks += 1
            continue
        
        # Skip empty content
        if not content or len(content.strip()) < 50:
            skipped_chunks += 1
            continue
        
        try:
            result = process_clause(
                clause_text=content,
                org_name=org_name,
                chunk_id=chunk_id
            )
            
            # Add chunk metadata
            result['chunk_metadata'] = {
                'chapter': chunk.get('chapter'),
                'regulation': chunk.get('regulation'),
                'section_type': section_type,
            }
            
            results.append(result)
            
            if result['is_applicable']:
                applicable_chunks += 1
                total_actionables += result['actionable_count']
                
        except Exception as e:
            print(f"\nError processing {chunk_id}: {e}")
            results.append({
                'chunk_id': chunk_id,
                'error': str(e),
                'is_applicable': False,
                'actionables': [],
                'actionable_count': 0,
            })
    
    return {
        'org_name': org_name,
        'total_chunks_processed': len(results),
        'skipped_chunks': skipped_chunks,
        'applicable_chunks': applicable_chunks,
        'total_actionables': total_actionables,
        'results': results,
        'timestamp': datetime.now().isoformat(),
    }


def generate_compliance_report(output: dict) -> str:
    """Generate a readable compliance report"""
    
    report = []
    report.append("=" * 70)
    report.append(f"COMPLIANCE REPORT: {output['org_name']}")
    report.append(f"Generated: {output['timestamp']}")
    report.append("=" * 70)
    report.append("")
    report.append("SUMMARY")
    report.append("-" * 70)
    report.append(f"Total Chunks Processed: {output['total_chunks_processed']}")
    report.append(f"Skipped Chunks: {output['skipped_chunks']}")
    report.append(f"Applicable Chunks: {output['applicable_chunks']}")
    report.append(f"TOTAL ACTIONABLES: {output['total_actionables']}")
    report.append("")
    report.append("=" * 70)
    report.append("DETAILED ACTIONABLES")
    report.append("=" * 70)
    
    actionable_num = 1
    for result in output['results']:
        if result.get('is_applicable') and result.get('actionables'):
            chunk_meta = result.get('chunk_metadata', {})
            chapter = chunk_meta.get('chapter', 'N/A')
            regulation = chunk_meta.get('regulation', 'N/A')
            
            report.append("")
            report.append(f"[Chapter {chapter} | Regulation {regulation}]")
            report.append(f"Type: {result.get('clause_type', 'N/A')}")
            
            for action in result['actionables']:
                report.append(f"  {actionable_num}. {action}")
                actionable_num += 1
            
            report.append("")
    
    return "\n".join(report)


def save_results(output: dict, org_name: str, output_dir: str = "data"):
    """Save results to JSON and text files"""
    
    # Create safe filename
    safe_name = org_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON
    json_file = os.path.join(output_dir, f"compliance_{safe_name}_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {json_file}")
    
    # Save readable report
    report = generate_compliance_report(output)
    txt_file = os.path.join(output_dir, f"compliance_{safe_name}_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Saved Report: {txt_file}")
    
    return json_file, txt_file


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate compliance items from PDF chunks")
    parser.add_argument("--org", choices=["HDFC", "Navi", "both"], default="both",
                       help="Organization to process")
    parser.add_argument("--chunks", default="data/1758886606773_chunks.json",
                       help="Path to chunks JSON file")
    parser.add_argument("--output", default="data",
                       help="Output directory")
    parser.add_argument("--limit", type=int, default=0,
                       help="Limit chunks to process (0 = all)")
    
    args = parser.parse_args()
    
    # Load chunks
    chunks_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), args.chunks)
    print(f"Loading chunks from: {chunks_path}")
    chunks = load_chunks(chunks_path)
    print(f"Loaded {len(chunks)} chunks")
    
    # Apply limit if specified
    if args.limit > 0:
        chunks = chunks[:args.limit]
        print(f"Limited to {len(chunks)} chunks")
    
    # Process for each organization
    orgs = []
    if args.org in ["HDFC", "both"]:
        orgs.append("HDFC AMC")
    if args.org in ["Navi", "both"]:
        orgs.append("Navi AMC")
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), args.output)
    
    for org in orgs:
        print(f"\n\nProcessing for {org}...")
        output = process_all_chunks(chunks, org)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"RESULTS FOR {org}")
        print(f"{'='*60}")
        print(f"Chunks Processed: {output['total_chunks_processed']}")
        print(f"Applicable: {output['applicable_chunks']}")
        print(f"TOTAL ACTIONABLES: {output['total_actionables']}")
        
        # Save results
        save_results(output, org, output_dir)
    
    print("\n\nDone!")


if __name__ == "__main__":
    main()

