import sqlite3
import json
from datetime import datetime
import os

DB_PATH = 'chatbot.db'

def get_all_resolved_cases():
    """Get all resolved cases from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM resolution_cases
        ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    cases = []
    for row in rows:
        cases.append({
            'id': row['id'],
            'conversation_id': row['conversation_id'],
            'problem_type': row['problem_type'],
            'user_query': row['user_query'],
            'resolution_steps': json.loads(row['resolution_steps']),
            'agent_messages': json.loads(row['agent_messages']),
            'intent': row['intent'],
            'entities': json.loads(row['entities']) if row['entities'] else [],
            'created_at': row['created_at']
        })
    
    return cases


def generate_nlu_training_data(cases):
    """Generate NLU training data from resolved cases"""
    nlu_data = {
        'version': '3.1',
        'nlu': []
    }
    
    # Keywords to filter out escalation requests
    escalation_keywords = [
        'agent', 'human', 'representative', 'person', 
        'talk to', 'speak to', 'connect me', 'transfer'
    ]
    
    def is_escalation_request(text):
        """Check if text is an escalation request"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in escalation_keywords)
    
    # Group by intent/problem_type
    intent_examples = {}
    
    for case in cases:
        intent = case['intent'] or case['problem_type']
        
        # Clean intent name
        intent = intent.replace(' ', '_').replace('-', '_').lower()
        
        if intent not in intent_examples:
            intent_examples[intent] = set()
        
        # Add user query if it's not an escalation request
        if case['user_query'] and case['user_query'].strip():
            query = case['user_query'].strip()
            
            if not is_escalation_request(query):
                intent_examples[intent].add(query)
                
                # Generate variations
                query_lower = query.lower()
                if query_lower != query:
                    intent_examples[intent].add(query_lower)
                
                # Remove question marks for variation
                if '?' in query:
                    intent_examples[intent].add(query.replace('?', ''))
    
    # Format for Rasa
    for intent, examples_set in intent_examples.items():
        if examples_set and len(examples_set) > 0:
            examples = list(examples_set)
            examples_text = '\n    - '.join(examples)
            nlu_data['nlu'].append({
                'intent': intent,
                'examples': f"|\n    - {examples_text}"
            })
    
    return nlu_data


def generate_response_templates(cases):
    """Generate response templates from agent messages"""
    responses = {}
    
    for case in cases:
        intent = case['intent'] or case['problem_type']
        response_key = f"utter_{intent}"
        
        if response_key not in responses:
            responses[response_key] = []
        
        # Use first agent message as template
        if case['agent_messages'] and len(case['agent_messages']) > 0:
            first_message = case['agent_messages'][0]
            
            # Avoid duplicates
            if not any(r['text'] == first_message for r in responses[response_key]):
                responses[response_key].append({
                    'text': first_message
                })
    
    return responses


def generate_stories(cases):
    """Generate stories from resolved cases"""
    stories = {
        'version': '3.1',
        'stories': []
    }
    
    for idx, case in enumerate(cases[:10]):  # Limit to 10 stories
        intent = case['intent'] or case['problem_type']
        
        story = {
            'story': f"case_{intent}_{idx}",
            'steps': [
                {'intent': intent},
                {'action': f"utter_{intent}"}
            ]
        }
        
        stories['stories'].append(story)
    
    return stories


def save_training_data(nlu_data, responses, stories):
    """Save generated training data to files"""
    
    # Create backup directory
    backup_dir = 'data/generated_training'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save NLU data
    nlu_file = f"{backup_dir}/nlu_from_cases_{timestamp}.yml"
    with open(nlu_file, 'w') as f:
        f.write(f"version: \"{nlu_data['version']}\"\n\n")
        f.write("nlu:\n")
        for item in nlu_data['nlu']:
            f.write(f"- intent: {item['intent']}\n")
            f.write(f"  examples: {item['examples']}\n\n")
    
    print(f"✅ NLU data saved: {nlu_file}")
    
    # Save responses
    responses_file = f"{backup_dir}/responses_from_cases_{timestamp}.yml"
    with open(responses_file, 'w') as f:
        f.write("responses:\n")
        for response_key, response_list in responses.items():
            f.write(f"  {response_key}:\n")
            for resp in response_list:
                f.write(f"  - text: \"{resp['text']}\"\n")
    
    print(f"✅ Responses saved: {responses_file}")
    
    # Save stories
    stories_file = f"{backup_dir}/stories_from_cases_{timestamp}.yml"
    with open(stories_file, 'w') as f:
        f.write(f"version: \"{stories['version']}\"\n\n")
        f.write("stories:\n")
        for story in stories['stories']:
            f.write(f"- story: {story['story']}\n")
            f.write(f"  steps:\n")
            for step in story['steps']:
                if 'intent' in step:
                    f.write(f"  - intent: {step['intent']}\n")
                elif 'action' in step:
                    f.write(f"  - action: {step['action']}\n")
            f.write("\n")
    
    print(f"✅ Stories saved: {stories_file}")
    
    return nlu_file, responses_file, stories_file


def merge_with_existing_data(nlu_file, responses_file):
    """Merge generated data with existing training data"""
    
    # Merge NLU data
    try:
        with open('data/nlu.yml', 'r') as f:
            existing_nlu = f.read()
        
        with open(nlu_file, 'r') as f:
            new_nlu = f.read()
        
        # Append new data
        with open('data/nlu.yml', 'a') as f:
            f.write("\n# === Generated from agent resolutions ===\n")
            f.write(new_nlu.split('nlu:\n')[1])  # Skip header
        
        print("✅ NLU data merged into data/nlu.yml")
    except Exception as e:
        print(f"⚠️ Could not merge NLU data: {e}")
    
    # Merge responses into domain
    try:
        with open('domain.yml', 'r') as f:
            domain_content = f.read()
        
        with open(responses_file, 'r') as f:
            new_responses = f.read()
        
        # Append new responses
        if 'responses:' in domain_content:
            with open('domain.yml', 'a') as f:
                f.write("\n# === Generated from agent resolutions ===\n")
                f.write(new_responses.split('responses:\n')[1])  # Skip header
        
        print("✅ Responses merged into domain.yml")
    except Exception as e:
        print(f"⚠️ Could not merge responses: {e}")


def generate_training_summary():
    """Generate a summary report of training data"""
    cases = get_all_resolved_cases()
    
    summary = {
        'total_cases': len(cases),
        'intents_covered': len(set(c['intent'] or c['problem_type'] for c in cases)),
        'problem_types': {}
    }
    
    for case in cases:
        ptype = case['problem_type']
        if ptype not in summary['problem_types']:
            summary['problem_types'][ptype] = 0
        summary['problem_types'][ptype] += 1
    
    return summary


def main():
    """Main function to generate training data from resolutions"""
    print("\n🤖 AI Training Data Generator")
    print("=" * 50)
    
    # Get resolved cases
    cases = get_all_resolved_cases()
    print(f"\n📊 Found {len(cases)} resolved cases")
    
    if len(cases) == 0:
        print("⚠️ No resolved cases found. Resolve some cases first!")
        return
    
    # Generate training data
    print("\n🔄 Generating training data...")
    nlu_data = generate_nlu_training_data(cases)
    responses = generate_response_templates(cases)
    stories = generate_stories(cases)
    
    # Save training data
    print("\n💾 Saving training data...")
    nlu_file, responses_file, stories_file = save_training_data(nlu_data, responses, stories)
    
    # Generate summary
    summary = generate_training_summary()
    print("\n📈 Training Summary:")
    print(f"   Total Cases: {summary['total_cases']}")
    print(f"   Unique Intents: {summary['intents_covered']}")
    print(f"\n   Problem Types Distribution:")
    for ptype, count in summary['problem_types'].items():
        print(f"      - {ptype}: {count} cases")
    
    # Ask to merge
    print("\n" + "=" * 50)
    merge = input("\n🔀 Merge with existing training data? (yes/no): ").strip().lower()
    
    if merge == 'yes':
        merge_with_existing_data(nlu_file, responses_file)
        print("\n✅ Training data merged successfully!")
        print("\n🚀 Next steps:")
        print("   1. Review the merged data in data/nlu.yml and domain.yml")
        print("   2. Run: rasa train")
        print("   3. Test the improved bot!")
    else:
        print("\n📁 Training data saved in data/generated_training/")
        print("   You can manually review and merge it later.")
    
    print("\n" + "=" * 50)


if __name__ == '__main__':
    main()
