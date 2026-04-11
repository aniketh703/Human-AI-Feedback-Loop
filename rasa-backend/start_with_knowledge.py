"""
Startup script that initializes knowledge base and starts Rasa
"""

import os
import sys
import subprocess
import argparse
import time


def main():
    parser = argparse.ArgumentParser(description='Start Rasa with Knowledge Base')
    parser.add_argument(
        '--website-url',
        type=str,
        default='https://your-website.com',
        help='Website URL to learn from'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Force refresh the knowledge base'
    )
    parser.add_argument(
        '--train',
        action='store_true',
        help='Train the Rasa model before starting'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5005,
        help='Port for Rasa server (default: 5005)'
    )
    parser.add_argument(
        '--actions-port',
        type=int,
        default=5055,
        help='Port for action server (default: 5055)'
    )
    
    args = parser.parse_args()
    
    # Set environment variable for website URL
    os.environ['WEBSITE_URL'] = args.website_url
    
    print(f"\n{'='*60}")
    print(f"  Starting Rasa with Plug-and-Play Knowledge Base")
    print(f"{'='*60}")
    print(f"  Website: {args.website_url}")
    print(f"  Rasa Port: {args.port}")
    print(f"  Actions Port: {args.actions_port}")
    print(f"{'='*60}\n")
    
    # Initialize knowledge base
    print("Step 1: Initializing knowledge base...")
    try:
        # Add current directory to path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from actions.website_knowledge import initialize_knowledge_base
        
        kb = initialize_knowledge_base(args.website_url, force_refresh=args.refresh)
        print(f"✅ Knowledge base ready: {len(kb.chunks)} chunks from {len(kb.visited_urls)} pages\n")
    except ImportError as e:
        print(f"⚠️ Could not initialize knowledge base: {e}")
        print("   The chatbot will work without website knowledge.")
        print("   Install dependencies with: pip install -r requirements.txt\n")
    except Exception as e:
        print(f"⚠️ Error initializing knowledge base: {e}")
        print("   Continuing without website knowledge...\n")
    
    # Train if requested
    if args.train:
        print("Step 2: Training Rasa model...")
        try:
            subprocess.run(['rasa', 'train'], check=True)
            print("✅ Training complete\n")
        except subprocess.CalledProcessError as e:
            print(f"❌ Training failed: {e}")
            return
        except FileNotFoundError:
            print("❌ Rasa not found. Make sure Rasa is installed.")
            return
    
    # Start action server in background
    print("Step 3: Starting action server...")
    action_env = {**os.environ, 'WEBSITE_URL': args.website_url}
    
    try:
        action_process = subprocess.Popen(
            ['rasa', 'run', 'actions', '--port', str(args.actions_port)],
            env=action_env
        )
        print(f"✅ Action server starting on port {args.actions_port}")
        time.sleep(3)  # Wait for action server to start
    except FileNotFoundError:
        print("❌ Rasa not found. Make sure Rasa is installed.")
        return
    
    # Start Rasa server
    print(f"\nStep 4: Starting Rasa server on port {args.port}...")
    print("="*60)
    print("  Chatbot is ready! Press Ctrl+C to stop.")
    print("="*60 + "\n")
    
    try:
        subprocess.run(
            [
                'rasa', 'run',
                '--enable-api',
                '--cors', '*',
                '--port', str(args.port),
                '--endpoints', 'endpoints.yml',
                '--credentials', 'credentials.yml'
            ],
            env=action_env,
            check=True
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting Rasa server: {e}")
    finally:
        print("Stopping action server...")
        action_process.terminate()
        action_process.wait()
        print("✅ Shutdown complete")


if __name__ == '__main__':
    main()
