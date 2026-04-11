"""
Initialize Knowledge Base Script
Run this to crawl your website and build the knowledge base.

Usage:
    python init_knowledge.py https://your-website.com
    python init_knowledge.py https://your-website.com --refresh
"""

import sys
import argparse
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from actions.website_knowledge import initialize_knowledge_base


def main():
    parser = argparse.ArgumentParser(
        description='Initialize the chatbot knowledge base from a website'
    )
    parser.add_argument(
        'url',
        help='The base URL of the website to crawl'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Force refresh the cache'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=100,
        help='Maximum number of pages to crawl (default: 100)'
    )
    parser.add_argument(
        '--test-query',
        type=str,
        help='Test query to run after initialization'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  Knowledge Base Initialization")
    print(f"{'='*60}")
    print(f"  URL: {args.url}")
    print(f"  Refresh: {args.refresh}")
    print(f"  Max Pages: {args.max_pages}")
    print(f"{'='*60}\n")
    
    # Initialize knowledge base
    kb = initialize_knowledge_base(args.url, force_refresh=args.refresh)
    
    print(f"\n{'='*60}")
    print(f"  Initialization Complete!")
    print(f"{'='*60}")
    print(f"  Pages crawled: {len(kb.visited_urls)}")
    print(f"  Content chunks: {len(kb.chunks)}")
    print(f"{'='*60}\n")
    
    # Test query if provided
    if args.test_query:
        print(f"\nTesting query: '{args.test_query}'")
        print("-" * 40)
        results = kb.search(args.test_query, top_k=3)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['title']}")
            print(f"   Score: {result['score']:.4f}")
            print(f"   URL: {result['url']}")
            print(f"   Text: {result['text'][:200]}...")
    
    # Interactive mode
    print("\n" + "="*60)
    print("  Interactive Test Mode (type 'quit' to exit)")
    print("="*60 + "\n")
    
    while True:
        try:
            query = input("\nYour question: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not query:
                continue
            
            answer = kb.get_answer(query)
            print(f"\nAnswer:\n{answer}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            break


if __name__ == '__main__':
    main()
