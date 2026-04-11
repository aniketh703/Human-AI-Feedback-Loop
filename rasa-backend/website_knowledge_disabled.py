"""
Website Knowledge Base - Plug and Play RAG System
Automatically scrapes website content and provides intelligent responses
"""

import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import re

# Vector store and embeddings
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss


class WebsiteKnowledgeBase:
    """
    Plug-and-play knowledge base that learns from website content.
    """
    
    def __init__(
        self,
        base_url: str,
        cache_dir: str = None,
        max_pages: int = 100,
        chunk_size: int = 500
    ):
        # Use absolute path for cache directory
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "website_cache")
        self.base_url = base_url
        self.cache_dir = cache_dir
        self.max_pages = max_pages
        self.chunk_size = chunk_size
        self.visited_urls = set()
        self.documents = []
        self.chunks = []
        self.embeddings = None
        self.index = None
        
        # Initialize embedding model (runs locally, no API needed)
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load cached data if available
        self._load_cache()
    
    def _get_cache_key(self) -> str:
        """Generate cache key based on base URL"""
        return hashlib.md5(self.base_url.encode()).hexdigest()
    
    def _load_cache(self) -> bool:
        """Load cached embeddings and documents"""
        cache_key = self._get_cache_key()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}_data.json")
        index_file = os.path.join(self.cache_dir, f"{cache_key}_index.faiss")
        
        if os.path.exists(cache_file) and os.path.exists(index_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.documents = data.get('documents', [])
                    self.chunks = data.get('chunks', [])
                    self.visited_urls = set(data.get('visited_urls', []))
                
                self.index = faiss.read_index(index_file)
                print(f"Loaded {len(self.chunks)} cached chunks from {len(self.visited_urls)} pages")
                return True
            except Exception as e:
                print(f"Error loading cache: {e}")
        return False
    
    def _save_cache(self):
        """Save embeddings and documents to cache"""
        cache_key = self._get_cache_key()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}_data.json")
        index_file = os.path.join(self.cache_dir, f"{cache_key}_index.faiss")
        
        try:
            data = {
                'documents': self.documents,
                'chunks': self.chunks,
                'visited_urls': list(self.visited_urls)
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if self.index is not None:
                faiss.write_index(self.index, index_file)
            
            print(f"Cached {len(self.chunks)} chunks to disk")
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return url_domain == base_domain
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?;:\-\'\"()]', '', text)
        return text.strip()
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract meaningful content from HTML"""
        # Remove script, style, nav, footer, header elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'meta', 'link']):
            element.decompose()
        
        # Extract title
        title = soup.title.string if soup.title else ""
        title = self._clean_text(title) if title else urlparse(url).path
        
        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        
        if main_content:
            # Get all text
            text = main_content.get_text(separator=' ', strip=True)
            text = self._clean_text(text)
        else:
            text = ""
        
        # Extract headings for context
        headings = []
        for h in soup.find_all(['h1', 'h2', 'h3']):
            heading_text = self._clean_text(h.get_text())
            if heading_text:
                headings.append(heading_text)
        
        return {
            'url': url,
            'title': title,
            'content': text,
            'headings': headings
        }
    
    def _chunk_text(self, document: Dict) -> List[Dict]:
        """Split document into smaller chunks for better retrieval"""
        content = document['content']
        chunks = []
        
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < self.chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk.strip():
                    chunks.append({
                        'text': current_chunk.strip(),
                        'url': document['url'],
                        'title': document['title'],
                        'headings': document['headings']
                    })
                current_chunk = sentence
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'url': document['url'],
                'title': document['title'],
                'headings': document['headings']
            })
        
        return chunks
    
    def crawl_website(self, force_refresh: bool = False):
        """Crawl the website and extract content"""
        if self.chunks and not force_refresh:
            print(f"Using cached data. Set force_refresh=True to re-crawl.")
            return
        
        print(f"Starting to crawl: {self.base_url}")
        
        self.visited_urls = set()
        self.documents = []
        self.chunks = []
        
        urls_to_visit = [self.base_url]
        
        while urls_to_visit and len(self.visited_urls) < self.max_pages:
            url = urls_to_visit.pop(0)
            
            if url in self.visited_urls:
                continue
            
            try:
                print(f"Crawling: {url}")
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; KnowledgeBot/1.0)'
                })
                
                if response.status_code != 200:
                    continue
                
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    continue
                
                self.visited_urls.add(url)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract content
                document = self._extract_content(soup, url)
                
                if document['content'] and len(document['content']) > 50:
                    self.documents.append(document)
                    
                    # Chunk the document
                    doc_chunks = self._chunk_text(document)
                    self.chunks.extend(doc_chunks)
                
                # Find more links
                for link in soup.find_all('a', href=True):
                    next_url = urljoin(url, link['href'])
                    next_url = next_url.split('#')[0]  # Remove fragments
                    next_url = next_url.split('?')[0]  # Remove query params
                    
                    if (self._is_valid_url(next_url) and 
                        next_url not in self.visited_urls and
                        next_url not in urls_to_visit):
                        urls_to_visit.append(next_url)
                        
            except Exception as e:
                print(f"Error crawling {url}: {e}")
                continue
        
        print(f"Crawled {len(self.visited_urls)} pages, extracted {len(self.chunks)} chunks")
        
        # Build embeddings
        self._build_index()
        
        # Save to cache
        self._save_cache()
    
    def _build_index(self):
        """Build FAISS index from chunks"""
        if not self.chunks:
            print("No chunks to index")
            return
        
        print("Building embeddings...")
        
        # Create embeddings for all chunks
        texts = [chunk['text'] for chunk in self.chunks]
        self.embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        
        # Build FAISS index
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(self.embeddings).astype('float32'))
        
        print(f"Built index with {self.index.ntotal} vectors")
    
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search for relevant content"""
        if self.index is None or not self.chunks:
            return []
        
        # Encode query
        query_embedding = self.embedding_model.encode([query])
        
        # Search
        distances, indices = self.index.search(
            np.array(query_embedding).astype('float32'), 
            top_k
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                results.append({
                    'text': chunk['text'],
                    'url': chunk['url'],
                    'title': chunk['title'],
                    'score': float(distances[0][i])
                })
        
        return results
    
    def get_answer(self, query: str, top_k: int = 3) -> str:
        """Get an answer based on website content"""
        results = self.search(query, top_k)
        
        if not results:
            return None
        
        # Combine relevant chunks into context
        context_parts = []
        sources = set()
        
        for result in results:
            context_parts.append(f"From '{result['title']}':\n{result['text']}")
            sources.add(result['url'])
        
        context = "\n\n".join(context_parts)
        
        # Format response
        response = f"Based on our website content:\n\n{results[0]['text']}"
        
        if len(results) > 1:
            response += f"\n\nAdditional information:\n{results[1]['text'][:200]}..."
        
        response += f"\n\n📄 Source: {results[0]['url']}"
        
        return response


# Singleton instance
_knowledge_base: Optional[WebsiteKnowledgeBase] = None


def get_knowledge_base(base_url: str = None) -> WebsiteKnowledgeBase:
    """Get or create knowledge base instance"""
    global _knowledge_base
    
    if _knowledge_base is None and base_url:
        _knowledge_base = WebsiteKnowledgeBase(base_url)
        _knowledge_base.crawl_website()
    
    return _knowledge_base


def initialize_knowledge_base(base_url: str, force_refresh: bool = False):
    """Initialize the knowledge base with a website URL"""
    global _knowledge_base
    _knowledge_base = WebsiteKnowledgeBase(base_url)
    _knowledge_base.crawl_website(force_refresh=force_refresh)
    return _knowledge_base
