"""
Auto-Generate Rasa Training Data from Website Scraping
======================================================
This script automatically creates NLU, domain, and stories files
based on scraped website content.

Usage:
    python auto_generate_training.py https://your-website.com
    python auto_generate_training.py https://your-website.com --refresh
"""

import os
import sys
import json
import re
import yaml
import argparse
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict

# Output directories
RASA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(RASA_DIR, "data")
GENERATED_DIR = os.path.join(DATA_DIR, "generated_training")
CACHE_DIR = os.path.join(RASA_DIR, "website_cache")


class WebsiteScraper:
    """Scrape website content for training data generation"""
    
    def __init__(self, base_url: str, max_pages: int = 50):
        self.base_url = base_url
        self.max_pages = max_pages
        self.visited_urls = set()
        self.pages = []
        
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return url_domain == base_domain
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_page_data(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract structured data from a page"""
        # Remove non-content elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'meta', 'link', 'noscript']):
            element.decompose()
        
        # Get title
        title = ""
        if soup.title:
            title = self._clean_text(soup.title.string or "")
        if not title:
            h1 = soup.find('h1')
            title = self._clean_text(h1.get_text()) if h1 else urlparse(url).path
        
        # Get headings (for topic extraction)
        headings = []
        for h in soup.find_all(['h1', 'h2', 'h3']):
            text = self._clean_text(h.get_text())
            if text and len(text) > 3:
                headings.append(text)
        
        # Get paragraphs
        paragraphs = []
        for p in soup.find_all(['p', 'li']):
            text = self._clean_text(p.get_text())
            if text and len(text) > 20:
                paragraphs.append(text)
        
        # Get FAQ-style content (questions/answers)
        faqs = self._extract_faqs(soup)
        
        # Get main content
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        full_text = ""
        if main_content:
            full_text = self._clean_text(main_content.get_text(separator=' ', strip=True))
        
        return {
            'url': url,
            'title': title,
            'headings': headings,
            'paragraphs': paragraphs[:20],  # Limit paragraphs
            'faqs': faqs,
            'full_text': full_text[:5000]  # Limit full text
        }
    
    def _extract_faqs(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract FAQ-style Q&A pairs"""
        faqs = []
        
        # Look for FAQ sections
        faq_containers = soup.find_all(['div', 'section'], class_=re.compile(r'faq|question|accordion', re.I))
        
        for container in faq_containers:
            questions = container.find_all(['h3', 'h4', 'dt', 'button'], class_=re.compile(r'question|title', re.I))
            answers = container.find_all(['p', 'dd', 'div'], class_=re.compile(r'answer|content|body', re.I))
            
            for q, a in zip(questions, answers):
                q_text = self._clean_text(q.get_text())
                a_text = self._clean_text(a.get_text())
                if q_text and a_text:
                    faqs.append({'question': q_text, 'answer': a_text})
        
        # Also look for definition lists
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                q_text = self._clean_text(dt.get_text())
                a_text = self._clean_text(dd.get_text())
                if q_text and a_text:
                    faqs.append({'question': q_text, 'answer': a_text})
        
        return faqs
    
    def crawl(self, force_refresh: bool = False) -> List[Dict]:
        """Crawl the website"""
        cache_key = hashlib.md5(self.base_url.encode()).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}_scraped.json")
        
        # Check cache
        if not force_refresh and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pages = data.get('pages', [])
                    self.visited_urls = set(data.get('visited_urls', []))
                    print(f"📦 Loaded {len(self.pages)} cached pages")
                    return self.pages
            except Exception as e:
                print(f"⚠️ Cache load error: {e}")
        
        print(f"🌐 Starting to crawl: {self.base_url}")
        
        urls_to_visit = [self.base_url]
        
        while urls_to_visit and len(self.visited_urls) < self.max_pages:
            url = urls_to_visit.pop(0)
            
            if url in self.visited_urls:
                continue
            
            try:
                print(f"  📄 Crawling: {url}")
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; TrainingDataBot/1.0)'
                })
                
                if response.status_code != 200:
                    continue
                
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    continue
                
                self.visited_urls.add(url)
                
                soup = BeautifulSoup(response.text, 'html.parser')
                page_data = self._extract_page_data(soup, url)
                
                if page_data['full_text'] and len(page_data['full_text']) > 100:
                    self.pages.append(page_data)
                
                # Find more links
                for link in soup.find_all('a', href=True):
                    next_url = urljoin(url, link['href'])
                    next_url = next_url.split('#')[0]
                    next_url = next_url.split('?')[0]
                    
                    if (self._is_valid_url(next_url) and 
                        next_url not in self.visited_urls and
                        next_url not in urls_to_visit):
                        urls_to_visit.append(next_url)
                        
            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue
        
        print(f"✅ Crawled {len(self.pages)} pages")
        
        # Save to cache
        os.makedirs(CACHE_DIR, exist_ok=True)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'pages': self.pages,
                    'visited_urls': list(self.visited_urls),
                    'timestamp': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Cache save error: {e}")
        
        return self.pages


class TrainingDataGenerator:
    """Generate Rasa training data from scraped content"""
    
    def __init__(self, pages: List[Dict], website_name: str = "website"):
        self.pages = pages
        self.website_name = self._sanitize_name(website_name)
        self.topics = {}
        self.intents = []
        self.responses = {}
        self.stories = []
        
    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in intent/response names"""
        # Remove common suffixes
        name = re.sub(r'\s*[-|–]\s*.*$', '', name)  # Remove everything after dash
        name = re.sub(r'[^\w\s]', '', name)  # Remove special chars
        name = name.lower().strip()
        name = re.sub(r'\s+', '_', name)  # Replace spaces with underscore
        return name[:30] if name else "website"
    
    def _create_intent_name(self, topic: str) -> str:
        """Create a valid intent name from topic"""
        name = topic.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', '_', name.strip())
        return f"ask_{name[:40]}" if name else "ask_general"
    
    def _generate_question_variations(self, topic: str, content: str) -> List[str]:
        """Generate question variations for a topic"""
        topic_lower = topic.lower()
        
        # Base question patterns
        patterns = [
            f"what is {topic_lower}",
            f"tell me about {topic_lower}",
            f"explain {topic_lower}",
            f"how does {topic_lower} work",
            f"what does {topic_lower} do",
            f"i want to know about {topic_lower}",
            f"can you explain {topic_lower}",
            f"what are {topic_lower}",
            f"help with {topic_lower}",
            f"information about {topic_lower}",
            f"{topic_lower} info",
            f"{topic_lower} details",
            f"more about {topic_lower}",
        ]
        
        # Add variations based on common words in topic
        words = topic_lower.split()
        if len(words) > 1:
            patterns.append(f"what is {words[0]}")
            patterns.append(f"tell me about {words[-1]}")
        
        return patterns[:10]  # Limit to 10 variations
    
    def _extract_topics(self):
        """Extract topics from scraped pages"""
        print("🔍 Extracting topics from pages...")
        
        topic_content = defaultdict(lambda: {'headings': [], 'paragraphs': [], 'urls': []})
        
        for page in self.pages:
            # Use page title as a topic
            if page['title']:
                title = page['title']
                topic_content[title]['headings'].append(title)
                topic_content[title]['paragraphs'].extend(page['paragraphs'][:3])
                topic_content[title]['urls'].append(page['url'])
            
            # Use main headings as topics
            for heading in page['headings'][:5]:
                if len(heading) > 5 and len(heading) < 100:
                    topic_content[heading]['headings'].append(heading)
                    # Find relevant paragraphs
                    for p in page['paragraphs']:
                        if any(word.lower() in p.lower() for word in heading.split()[:2]):
                            topic_content[heading]['paragraphs'].append(p)
                            break
                    topic_content[heading]['urls'].append(page['url'])
            
            # Add FAQs directly as topics
            for faq in page['faqs']:
                topic_content[faq['question']]['paragraphs'].append(faq['answer'])
                topic_content[faq['question']]['urls'].append(page['url'])
        
        # Filter and deduplicate topics
        seen_intents = set()
        filtered_topics = {}
        
        for topic, data in topic_content.items():
            intent_name = self._create_intent_name(topic)
            
            # Skip if we already have this intent or if no content
            if intent_name in seen_intents:
                continue
            if not data['paragraphs']:
                continue
            if len(topic) < 5:
                continue
            
            seen_intents.add(intent_name)
            filtered_topics[topic] = {
                'intent': intent_name,
                'content': data['paragraphs'][0][:1000],  # First paragraph, limited
                'url': data['urls'][0] if data['urls'] else ""
            }
        
        self.topics = dict(list(filtered_topics.items())[:50])  # Limit to 50 topics
        print(f"  Found {len(self.topics)} unique topics")
    
    def _generate_intents(self):
        """Generate NLU intent examples"""
        print("📝 Generating NLU intents...")
        
        for topic, data in self.topics.items():
            questions = self._generate_question_variations(topic, data['content'])
            
            self.intents.append({
                'intent': data['intent'],
                'examples': questions
            })
        
        print(f"  Generated {len(self.intents)} intents")
    
    def _generate_responses(self):
        """Generate domain responses"""
        print("💬 Generating responses...")
        
        for topic, data in self.topics.items():
            response_name = f"utter_{data['intent']}"
            
            # Format response text
            content = data['content']
            if len(content) > 500:
                content = content[:500] + "..."
            
            response_text = f"**{topic}**\n\n{content}"
            
            if data['url']:
                response_text += f"\n\n📄 Learn more: {data['url']}"
            
            self.responses[response_name] = [{
                'text': response_text,
                'buttons': [
                    {'title': 'This helped!', 'payload': 'thanks'},
                    {'title': 'Talk to agent', 'payload': 'I want to talk to an agent'}
                ]
            }]
        
        print(f"  Generated {len(self.responses)} responses")
    
    def _generate_stories(self):
        """Generate story flows"""
        print("📖 Generating stories...")
        
        for topic, data in self.topics.items():
            story_name = data['intent'].replace('ask_', '')
            
            self.stories.append({
                'story': f"{story_name} question",
                'steps': [
                    {'intent': data['intent']},
                    {'action': f"utter_{data['intent']}"}
                ]
            })
        
        print(f"  Generated {len(self.stories)} stories")
    
    def generate(self):
        """Generate all training data"""
        print("\n" + "="*60)
        print("  Generating Rasa Training Data")
        print("="*60 + "\n")
        
        self._extract_topics()
        self._generate_intents()
        self._generate_responses()
        self._generate_stories()
        
        return {
            'intents': self.intents,
            'responses': self.responses,
            'stories': self.stories,
            'topics': self.topics
        }
    
    def save_files(self, output_dir: str = None):
        """Save generated training data to YAML files"""
        if output_dir is None:
            output_dir = GENERATED_DIR
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"\n💾 Saving files to {output_dir}")
        
        # Save NLU
        nlu_data = {
            'version': '3.1',
            'nlu': []
        }
        for intent_data in self.intents:
            nlu_data['nlu'].append({
                'intent': intent_data['intent'],
                'examples': '- ' + '\n- '.join(intent_data['examples'])
            })
        
        nlu_file = os.path.join(output_dir, f'nlu_generated.yml')
        with open(nlu_file, 'w', encoding='utf-8') as f:
            # Custom YAML formatting for NLU
            f.write("version: \"3.1\"\n\n")
            f.write(f"# Auto-generated from {self.website_name} on {timestamp}\n")
            f.write("# Add these intents to your main nlu.yml or import this file\n\n")
            f.write("nlu:\n")
            for intent_data in self.intents:
                f.write(f"- intent: {intent_data['intent']}\n")
                f.write("  examples: |\n")
                for example in intent_data['examples']:
                    f.write(f"    - {example}\n")
                f.write("\n")
        print(f"  ✅ {nlu_file}")
        
        # Save Domain additions
        domain_data = {
            'version': '3.1',
            'intents': [i['intent'] for i in self.intents],
            'responses': self.responses
        }
        
        domain_file = os.path.join(output_dir, f'domain_generated.yml')
        with open(domain_file, 'w', encoding='utf-8') as f:
            f.write("version: \"3.1\"\n\n")
            f.write(f"# Auto-generated from {self.website_name} on {timestamp}\n")
            f.write("# Merge these intents and responses into your main domain.yml\n\n")
            f.write("intents:\n")
            for intent_data in self.intents:
                f.write(f"  - {intent_data['intent']}\n")
            f.write("\nresponses:\n")
            for response_name, response_list in self.responses.items():
                f.write(f"  {response_name}:\n")
                for response in response_list:
                    f.write(f"  - text: |\n")
                    for line in response['text'].split('\n'):
                        f.write(f"      {line}\n")
                    if 'buttons' in response:
                        f.write("    buttons:\n")
                        for btn in response['buttons']:
                            f.write(f"    - title: \"{btn['title']}\"\n")
                            f.write(f"      payload: \"{btn['payload']}\"\n")
                f.write("\n")
        print(f"  ✅ {domain_file}")
        
        # Save Stories
        stories_file = os.path.join(output_dir, f'stories_generated.yml')
        with open(stories_file, 'w', encoding='utf-8') as f:
            f.write("version: \"3.1\"\n\n")
            f.write(f"# Auto-generated from {self.website_name} on {timestamp}\n")
            f.write("# Add these stories to your main stories.yml\n\n")
            f.write("stories:\n")
            for story in self.stories:
                f.write(f"- story: {story['story']}\n")
                f.write("  steps:\n")
                for step in story['steps']:
                    if 'intent' in step:
                        f.write(f"  - intent: {step['intent']}\n")
                    if 'action' in step:
                        f.write(f"  - action: {step['action']}\n")
                f.write("\n")
        print(f"  ✅ {stories_file}")
        
        # Save summary
        summary = {
            'website': self.website_name,
            'generated_at': timestamp,
            'stats': {
                'intents': len(self.intents),
                'responses': len(self.responses),
                'stories': len(self.stories),
                'topics': list(self.topics.keys())
            }
        }
        
        summary_file = os.path.join(output_dir, 'generation_summary.json')
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"  ✅ {summary_file}")
        
        return {
            'nlu': nlu_file,
            'domain': domain_file,
            'stories': stories_file,
            'summary': summary_file
        }


def merge_with_existing(generated_dir: str = GENERATED_DIR, backup: bool = True):
    """Merge generated training data with existing files"""
    print("\n" + "="*60)
    print("  Merging with Existing Training Data")
    print("="*60 + "\n")
    
    # Load generated files
    nlu_gen = os.path.join(generated_dir, 'nlu_generated.yml')
    domain_gen = os.path.join(generated_dir, 'domain_generated.yml')
    stories_gen = os.path.join(generated_dir, 'stories_generated.yml')
    
    if not all(os.path.exists(f) for f in [nlu_gen, domain_gen, stories_gen]):
        print("❌ Generated files not found. Run generation first.")
        return False
    
    # Backup existing files
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(DATA_DIR, f'backup_{timestamp}')
        os.makedirs(backup_dir, exist_ok=True)
        
        for file in ['nlu.yml', 'stories.yml']:
            src = os.path.join(DATA_DIR, file)
            if os.path.exists(src):
                import shutil
                shutil.copy(src, os.path.join(backup_dir, file))
        
        domain_src = os.path.join(RASA_DIR, 'domain.yml')
        if os.path.exists(domain_src):
            import shutil
            shutil.copy(domain_src, os.path.join(backup_dir, 'domain.yml'))
        
        print(f"📦 Backup created in {backup_dir}")
    
    # Read generated NLU content and append to existing
    with open(nlu_gen, 'r', encoding='utf-8') as f:
        gen_content = f.read()
    
    # Extract just the intents part (skip header)
    nlu_intents = '\n'.join(gen_content.split('\n')[6:])  # Skip header lines
    
    existing_nlu = os.path.join(DATA_DIR, 'nlu.yml')
    with open(existing_nlu, 'a', encoding='utf-8') as f:
        f.write("\n\n# === Auto-generated from website scraping ===\n")
        f.write(nlu_intents)
    print(f"✅ Appended to {existing_nlu}")
    
    # For domain and stories, we need to parse and merge properly
    # For now, just print instructions
    print("\n📋 Manual merge required for:")
    print(f"   - domain.yml: Add intents and responses from {domain_gen}")
    print(f"   - stories.yml: Add stories from {stories_gen}")
    print("\nOr import the generated files directly in your config.")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Auto-generate Rasa training data from website scraping'
    )
    parser.add_argument(
        'url',
        help='The base URL of the website to scrape'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Force refresh (re-scrape the website)'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=30,
        help='Maximum number of pages to scrape (default: 30)'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Automatically merge with existing training files'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for generated files'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  🤖 Rasa Training Data Auto-Generator")
    print("="*60)
    print(f"  URL: {args.url}")
    print(f"  Max Pages: {args.max_pages}")
    print(f"  Refresh: {args.refresh}")
    print("="*60 + "\n")
    
    # Step 1: Scrape website
    scraper = WebsiteScraper(args.url, max_pages=args.max_pages)
    pages = scraper.crawl(force_refresh=args.refresh)
    
    if not pages:
        print("❌ No pages scraped. Check the URL and try again.")
        return
    
    # Step 2: Generate training data
    website_name = urlparse(args.url).netloc
    generator = TrainingDataGenerator(pages, website_name)
    data = generator.generate()
    
    # Step 3: Save files
    files = generator.save_files(args.output_dir)
    
    # Step 4: Optionally merge
    if args.merge:
        merge_with_existing()
    
    print("\n" + "="*60)
    print("  ✅ Generation Complete!")
    print("="*60)
    print(f"\n  Generated files in: {args.output_dir or GENERATED_DIR}")
    print(f"  - {len(data['intents'])} intents")
    print(f"  - {len(data['responses'])} responses")
    print(f"  - {len(data['stories'])} stories")
    print("\n  Next steps:")
    print("  1. Review the generated files")
    print("  2. Merge with your existing training data")
    print("  3. Run: rasa train")
    print("  4. Test: rasa shell")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
