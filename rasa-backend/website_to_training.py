"""
Complete Website-to-Training Pipeline
=====================================
Scrapes a website and automatically updates Rasa training data,
then optionally retrains the model.

Usage:
    python website_to_training.py https://your-website.com
    python website_to_training.py https://your-website.com --train
    python website_to_training.py https://your-website.com --refresh --train
"""

import os
import sys
import subprocess
import argparse
import yaml
import shutil
from datetime import datetime

# Add current directory to path
RASA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(RASA_DIR, "data")
GENERATED_DIR = os.path.join(DATA_DIR, "generated_training")

sys.path.insert(0, RASA_DIR)

from auto_generate_training import WebsiteScraper, TrainingDataGenerator
from urllib.parse import urlparse


def load_yaml(filepath: str) -> dict:
    """Load YAML file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def save_yaml(filepath: str, data: dict):
    """Save YAML file with custom formatting"""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def backup_files():
    """Create backup of existing training files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(DATA_DIR, f'backup_{timestamp}')
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = [
        os.path.join(DATA_DIR, 'nlu.yml'),
        os.path.join(DATA_DIR, 'stories.yml'),
        os.path.join(RASA_DIR, 'domain.yml')
    ]
    
    for filepath in files_to_backup:
        if os.path.exists(filepath):
            shutil.copy(filepath, os.path.join(backup_dir, os.path.basename(filepath)))
    
    print(f"📦 Backup created: {backup_dir}")
    return backup_dir


def merge_nlu(generated_intents: list):
    """Merge generated NLU intents into existing nlu.yml"""
    nlu_file = os.path.join(DATA_DIR, 'nlu.yml')
    
    # Read existing file
    with open(nlu_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we already have auto-generated section
    marker = "# === Auto-generated from website scraping ==="
    if marker in content:
        # Remove old generated content
        content = content.split(marker)[0].rstrip()
    
    # Append new generated intents
    with open(nlu_file, 'w', encoding='utf-8') as f:
        f.write(content)
        f.write(f"\n\n{marker}\n")
        for intent_data in generated_intents:
            f.write(f"- intent: {intent_data['intent']}\n")
            f.write("  examples: |\n")
            for example in intent_data['examples']:
                f.write(f"    - {example}\n")
            f.write("\n")
    
    print(f"✅ Updated {nlu_file} with {len(generated_intents)} new intents")


def merge_domain(generated_intents: list, generated_responses: dict):
    """Merge generated domain data into existing domain.yml"""
    domain_file = os.path.join(RASA_DIR, 'domain.yml')
    
    # Load existing domain
    domain = load_yaml(domain_file)
    
    # Get existing intents
    existing_intents = set(domain.get('intents', []))
    
    # Add new intents
    new_intents = [i['intent'] for i in generated_intents]
    for intent in new_intents:
        if intent not in existing_intents:
            domain.setdefault('intents', []).append(intent)
    
    # Add new responses
    existing_responses = domain.get('responses', {})
    for response_name, response_data in generated_responses.items():
        if response_name not in existing_responses:
            domain.setdefault('responses', {})[response_name] = response_data
    
    # Save updated domain
    # Use custom formatting to preserve readability
    with open(domain_file, 'w', encoding='utf-8') as f:
        f.write('version: "3.1"\n\n')
        
        # Write intents
        f.write('intents:\n')
        for intent in domain.get('intents', []):
            f.write(f'  - {intent}\n')
        
        # Write entities if present
        if 'entities' in domain:
            f.write('\nentities:\n')
            for entity in domain['entities']:
                f.write(f'  - {entity}\n')
        
        # Write slots if present
        if 'slots' in domain:
            f.write('\nslots:\n')
            yaml.dump({'slots': domain['slots']}, f, default_flow_style=False, allow_unicode=True)
        
        # Write responses
        f.write('\nresponses:\n')
        for resp_name, resp_list in domain.get('responses', {}).items():
            f.write(f'  {resp_name}:\n')
            for resp in resp_list:
                if isinstance(resp.get('text'), str):
                    if '\n' in resp['text']:
                        f.write('  - text: |\n')
                        for line in resp['text'].split('\n'):
                            f.write(f'      {line}\n')
                    else:
                        f.write(f'  - text: "{resp["text"]}"\n')
                
                if 'image' in resp:
                    f.write(f'    image: "{resp["image"]}"\n')
                
                if 'buttons' in resp:
                    f.write('    buttons:\n')
                    for btn in resp['buttons']:
                        f.write(f'    - title: "{btn["title"]}"\n')
                        f.write(f'      payload: "{btn["payload"]}"\n')
        
        # Write actions if present
        if 'actions' in domain:
            f.write('\nactions:\n')
            for action in domain['actions']:
                f.write(f'  - {action}\n')
        
        # Write session config if present
        if 'session_config' in domain:
            f.write('\nsession_config:\n')
            for key, value in domain['session_config'].items():
                f.write(f'  {key}: {value}\n')
    
    print(f"✅ Updated {domain_file} with {len(new_intents)} new intents and {len(generated_responses)} new responses")


def merge_stories(generated_stories: list):
    """Merge generated stories into existing stories.yml"""
    stories_file = os.path.join(DATA_DIR, 'stories.yml')
    
    # Read existing file
    with open(stories_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we already have auto-generated section
    marker = "# === Auto-generated website stories ==="
    if marker in content:
        # Remove old generated content
        content = content.split(marker)[0].rstrip()
    
    # Append new generated stories
    with open(stories_file, 'w', encoding='utf-8') as f:
        f.write(content)
        f.write(f"\n\n{marker}\n")
        for story in generated_stories:
            f.write(f"- story: {story['story']}\n")
            f.write("  steps:\n")
            for step in story['steps']:
                if 'intent' in step:
                    f.write(f"  - intent: {step['intent']}\n")
                if 'action' in step:
                    f.write(f"  - action: {step['action']}\n")
            f.write("\n")
    
    print(f"✅ Updated {stories_file} with {len(generated_stories)} new stories")


def train_rasa():
    """Train the Rasa model"""
    print("\n🏋️ Training Rasa model...")
    print("="*60)
    
    try:
        result = subprocess.run(
            ['rasa', 'train'],
            cwd=RASA_DIR,
            capture_output=False
        )
        
        if result.returncode == 0:
            print("✅ Training completed successfully!")
            return True
        else:
            print("❌ Training failed")
            return False
    except Exception as e:
        print(f"❌ Error training: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Complete website-to-training pipeline for Rasa'
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
        '--train',
        action='store_true',
        help='Automatically train the model after updating'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup of existing files'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  🌐 Website-to-Training Pipeline")
    print("="*60)
    print(f"  URL: {args.url}")
    print(f"  Max Pages: {args.max_pages}")
    print(f"  Refresh: {args.refresh}")
    print(f"  Auto-train: {args.train}")
    print("="*60 + "\n")
    
    # Step 1: Backup existing files
    if not args.no_backup:
        backup_files()
    
    # Step 2: Scrape website
    print("\n📡 Step 1: Scraping website...")
    scraper = WebsiteScraper(args.url, max_pages=args.max_pages)
    pages = scraper.crawl(force_refresh=args.refresh)
    
    if not pages:
        print("❌ No pages scraped. Check the URL and try again.")
        return 1
    
    print(f"   Scraped {len(pages)} pages")
    
    # Step 3: Generate training data
    print("\n🔧 Step 2: Generating training data...")
    website_name = urlparse(args.url).netloc
    generator = TrainingDataGenerator(pages, website_name)
    data = generator.generate()
    
    # Also save standalone files for reference
    generator.save_files()
    
    # Step 4: Merge with existing files
    print("\n📝 Step 3: Merging with existing training data...")
    merge_nlu(data['intents'])
    merge_domain(data['intents'], data['responses'])
    merge_stories(data['stories'])
    
    # Step 5: Optionally train
    if args.train:
        print("\n🏋️ Step 4: Training model...")
        train_rasa()
    else:
        print("\n📋 Step 4: Skipped training (use --train to auto-train)")
    
    # Summary
    print("\n" + "="*60)
    print("  ✅ Pipeline Complete!")
    print("="*60)
    print(f"\n  📊 Generated:")
    print(f"     - {len(data['intents'])} intents")
    print(f"     - {len(data['responses'])} responses")
    print(f"     - {len(data['stories'])} stories")
    print(f"\n  📁 Files updated:")
    print(f"     - data/nlu.yml")
    print(f"     - data/stories.yml")
    print(f"     - domain.yml")
    print(f"\n  📁 Standalone files saved in:")
    print(f"     - {GENERATED_DIR}")
    
    if not args.train:
        print(f"\n  🚀 Next step: Run 'rasa train' to train the model")
    
    print("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
