from flask import Flask, request, jsonify
from flask_cors import CORS
from database import (
    get_pending_escalations, 
    get_escalation_by_id,
    save_agent_response,
    update_escalation_status,
    get_agent_responses,
    save_resolution_case,
    save_feedback,
    get_feedback_stats,
    get_low_rated_responses
)
from datetime import datetime
import sqlite3
import os

DB_PATH = 'chatbot.db'

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'API server is running'})


@app.route('/api/escalations/pending', methods=['GET'])
def get_pending():
    """Get all pending escalations for agent dashboard"""
    try:
        escalations = get_pending_escalations()
        return jsonify({
            'success': True,
            'count': len(escalations),
            'escalations': escalations
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/escalations/<conversation_id>', methods=['GET'])
def get_escalation(conversation_id):
    """Get specific escalation details"""
    try:
        escalation = get_escalation_by_id(conversation_id)
        if escalation:
            # Also get agent responses
            responses = get_agent_responses(conversation_id)
            escalation['agent_responses'] = responses
            return jsonify({'success': True, 'escalation': escalation})
        else:
            return jsonify({'success': False, 'error': 'Escalation not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/escalations/<conversation_id>/respond', methods=['POST'])
def respond_to_user(conversation_id):
    """Agent sends a response to user"""
    try:
        data = request.json
        agent_id = data.get('agent_id', 'agent_default')
        message = data.get('message')
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Save agent response
        save_agent_response(conversation_id, agent_id, message)
        
        # Update status to 'in_progress' if it was pending
        escalation = get_escalation_by_id(conversation_id)
        if escalation and escalation['status'] == 'pending':
            update_escalation_status(conversation_id, 'in_progress', agent_id)
        
        return jsonify({
            'success': True,
            'message': 'Response saved successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/escalations/<conversation_id>/resolve', methods=['POST'])
def resolve_escalation(conversation_id):
    """Mark escalation as resolved and save resolution case"""
    try:
        data = request.json
        agent_id = data.get('agent_id', 'agent_default')
        problem_type = data.get('problem_type', 'general')
        user_query = data.get('user_query', '')  # ADD THIS
        resolution_data = data.get('resolution_data', {})
        
        # Update status
        update_escalation_status(conversation_id, 'resolved', agent_id)
        
        # Get escalation details
        escalation = get_escalation_by_id(conversation_id)
        if escalation:
            # Use provided user query or extract from history
            if not user_query:
                if escalation['conversation_history']:
                    for msg in escalation['conversation_history']:
                        if msg['sender'] == 'user':
                            user_query = msg['text']
                            break
            
            # Get all agent responses
            agent_responses = get_agent_responses(conversation_id)
            
            # Save as resolution case for training
            save_resolution_case(
                conversation_id,
                problem_type,
                user_query,  # Use the provided or extracted query
                {
                    'steps': resolution_data.get('steps', []),
                    'messages': [r['message'] for r in agent_responses],
                    'intent': resolution_data.get('intent') or problem_type,
                    'entities': resolution_data.get('entities', [])
                }
            )
        
        return jsonify({
            'success': True,
            'message': 'Escalation resolved and case saved for training'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/messages', methods=['GET'])
def get_user_messages(user_id):
    """Get messages for a specific user (for chatbot to poll)"""
    try:
        conversation_id = request.args.get('conversation_id')
        if not conversation_id:
            return jsonify({'success': False, 'error': 'conversation_id required'}), 400
        
        # Get agent responses for this conversation
        responses = get_agent_responses(conversation_id)
        
        # Filter responses that haven't been delivered yet (simplified)
        # In production, you'd track delivery status
        return jsonify({
            'success': True,
            'messages': responses
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/escalations/<conversation_id>/user-message', methods=['POST'])
def save_user_message(conversation_id):
    """Save user message during live agent chat"""
    try:
        data = request.json
        user_id = data.get('user_id')
        message = data.get('message')
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Get current escalation and update conversation history
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT conversation_history FROM escalations WHERE conversation_id = ?', (conversation_id,))
        row = cursor.fetchone()
        
        if row:
            import json
            history = json.loads(row['conversation_history']) if row['conversation_history'] else []
            history.append({
                'sender': 'user',
                'text': message,
                'timestamp': datetime.now().isoformat()
            })
            cursor.execute(
                'UPDATE escalations SET conversation_history = ? WHERE conversation_id = ?',
                (json.dumps(history), conversation_id)
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'User message saved'})
        else:
            conn.close()
            return jsonify({'success': False, 'error': 'Escalation not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/escalations/by-user/<user_id>/latest', methods=['GET'])
def get_latest_user_escalation(user_id):
    """Get the latest escalation for a user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT conversation_id FROM escalations 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                'success': True,
                'conversation_id': row['conversation_id']
            })
        else:
            return jsonify({'success': False, 'error': 'No escalation found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback on a bot response"""
    try:
        data = request.json
        user_id = data.get('user_id')
        message_text = data.get('message_text')
        rating = data.get('rating')  # 1 = positive, 0 = negative
        conversation_id = data.get('conversation_id')
        intent = data.get('intent')
        comment = data.get('comment')
        
        if not user_id or not message_text or rating is None:
            return jsonify({'success': False, 'error': 'user_id, message_text, and rating are required'}), 400
        
        save_feedback(user_id, message_text, rating, conversation_id, intent, comment)
        
        return jsonify({
            'success': True,
            'message': 'Feedback submitted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback/stats', methods=['GET'])
def get_feedback_statistics():
    """Get feedback statistics for analytics"""
    try:
        stats = get_feedback_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/feedback/low-rated', methods=['GET'])
def get_low_rated():
    """Get responses with low ratings for improvement"""
    try:
        min_count = request.args.get('min_count', 2, type=int)
        responses = get_low_rated_responses(min_count)
        return jsonify({
            'success': True,
            'responses': responses
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 Starting API Server on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
