import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

DB_PATH = 'chatbot.db'

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Escalations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            conversation_history TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            agent_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Agent responses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES escalations(conversation_id)
        )
    ''')
    
    # Resolution cases table (for AI training)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resolution_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            problem_type TEXT,
            user_query TEXT NOT NULL,
            resolution_steps TEXT NOT NULL,
            agent_messages TEXT NOT NULL,
            intent TEXT,
            entities TEXT,
            solution_quality INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES escalations(conversation_id)
        )
    ''')
    
    # Training data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent TEXT NOT NULL,
            example_text TEXT NOT NULL,
            source TEXT DEFAULT 'agent',
            resolution_case_id INTEGER,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resolution_case_id) REFERENCES resolution_cases(id)
        )
    ''')
    
    # Feedback table for rating bot responses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            conversation_id TEXT,
            message_text TEXT NOT NULL,
            rating INTEGER NOT NULL,
            intent TEXT,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


def save_escalation_to_db(escalation_data: Dict):
    """Save escalation to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO escalations 
            (conversation_id, user_id, timestamp, conversation_history, reason, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            escalation_data['conversation_id'],
            escalation_data['user_id'],
            escalation_data['timestamp'],
            json.dumps(escalation_data['conversation_history']),
            escalation_data.get('reason', 'user_request'),
            escalation_data.get('status', 'pending')
        ))
        conn.commit()
        print(f"✅ Escalation saved to DB: {escalation_data['conversation_id']}")
    except sqlite3.IntegrityError:
        print(f"⚠️ Escalation already exists: {escalation_data['conversation_id']}")
    except Exception as e:
        print(f"❌ Error saving escalation to DB: {e}")
    finally:
        conn.close()


def get_pending_escalations() -> List[Dict]:
    """Get all pending escalations"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM escalations 
        WHERE status = 'pending' 
        ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    escalations = []
    for row in rows:
        escalations.append({
            'id': row['id'],
            'conversation_id': row['conversation_id'],
            'user_id': row['user_id'],
            'timestamp': row['timestamp'],
            'conversation_history': json.loads(row['conversation_history']),
            'reason': row['reason'],
            'status': row['status'],
            'created_at': row['created_at']
        })
    
    return escalations


def get_escalation_by_id(conversation_id: str) -> Optional[Dict]:
    """Get specific escalation by conversation ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM escalations WHERE conversation_id = ?
    ''', (conversation_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row['id'],
            'conversation_id': row['conversation_id'],
            'user_id': row['user_id'],
            'timestamp': row['timestamp'],
            'conversation_history': json.loads(row['conversation_history']),
            'reason': row['reason'],
            'status': row['status'],
            'agent_id': row['agent_id'],
            'created_at': row['created_at']
        }
    return None


def save_agent_response(conversation_id: str, agent_id: str, message: str):
    """Save agent's response"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO agent_responses 
        (conversation_id, agent_id, message, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (conversation_id, agent_id, message, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"✅ Agent response saved for: {conversation_id}")


def update_escalation_status(conversation_id: str, status: str, agent_id: str = None):
    """Update escalation status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if agent_id:
        cursor.execute('''
            UPDATE escalations 
            SET status = ?, agent_id = ?
            WHERE conversation_id = ?
        ''', (status, agent_id, conversation_id))
    else:
        cursor.execute('''
            UPDATE escalations 
            SET status = ?
            WHERE conversation_id = ?
        ''', (status, conversation_id))
    
    conn.commit()
    conn.close()
    print(f"✅ Escalation status updated: {conversation_id} -> {status}")


def get_agent_responses(conversation_id: str) -> List[Dict]:
    """Get all agent responses for a conversation"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM agent_responses 
        WHERE conversation_id = ?
        ORDER BY timestamp ASC
    ''', (conversation_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def save_resolution_case(conversation_id: str, problem_type: str, 
                        user_query: str, resolution_data: Dict):
    """Save a complete resolution case for future AI training"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO resolution_cases 
        (conversation_id, problem_type, user_query, resolution_steps, 
         agent_messages, intent, entities)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        conversation_id,
        problem_type,
        user_query,
        json.dumps(resolution_data.get('steps', [])),
        json.dumps(resolution_data.get('messages', [])),
        resolution_data.get('intent'),
        json.dumps(resolution_data.get('entities', []))
    ))
    
    conn.commit()
    conn.close()
    print(f"✅ Resolution case saved: {conversation_id}")


def save_feedback(user_id: str, message_text: str, rating: int, 
                  conversation_id: str = None, intent: str = None, comment: str = None):
    """Save user feedback on bot responses"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO feedback 
        (user_id, conversation_id, message_text, rating, intent, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, conversation_id, message_text, rating, intent, comment))
    
    conn.commit()
    conn.close()
    print(f"✅ Feedback saved: rating={rating}")


def get_feedback_stats() -> Dict:
    """Get feedback statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total feedback count
    cursor.execute('SELECT COUNT(*) FROM feedback')
    total = cursor.fetchone()[0]
    
    # Positive feedback (rating = 1)
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE rating = 1')
    positive = cursor.fetchone()[0]
    
    # Negative feedback (rating = 0)
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE rating = 0')
    negative = cursor.fetchone()[0]
    
    # Average rating
    cursor.execute('SELECT AVG(rating) FROM feedback')
    avg_rating = cursor.fetchone()[0] or 0
    
    # Feedback by intent (for problem areas)
    cursor.execute('''
        SELECT intent, COUNT(*) as count, AVG(rating) as avg_rating
        FROM feedback
        WHERE intent IS NOT NULL
        GROUP BY intent
        ORDER BY avg_rating ASC
    ''')
    by_intent = [{'intent': row[0], 'count': row[1], 'avg_rating': row[2]} 
                 for row in cursor.fetchall()]
    
    # Recent feedback
    cursor.execute('''
        SELECT * FROM feedback ORDER BY created_at DESC LIMIT 10
    ''')
    recent = [dict(zip(['id', 'user_id', 'conversation_id', 'message_text', 
                        'rating', 'intent', 'comment', 'created_at'], row)) 
              for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        'total': total,
        'positive': positive,
        'negative': negative,
        'satisfaction_rate': (positive / total * 100) if total > 0 else 0,
        'average_rating': avg_rating,
        'by_intent': by_intent,
        'recent': recent
    }


def get_low_rated_responses(min_count: int = 2) -> List[Dict]:
    """Get responses with low ratings for improvement"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT message_text, intent, COUNT(*) as feedback_count, AVG(rating) as avg_rating
        FROM feedback
        GROUP BY message_text
        HAVING feedback_count >= ? AND avg_rating < 0.5
        ORDER BY avg_rating ASC
    ''', (min_count,))
    
    results = [{'message': row[0], 'intent': row[1], 
                'feedback_count': row[2], 'avg_rating': row[3]} 
               for row in cursor.fetchall()]
    
    conn.close()
    return results


# Initialize database on import
if not os.path.exists(DB_PATH):
    init_db()