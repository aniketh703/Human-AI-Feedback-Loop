import sqlite3
import json

DB_PATH = 'chatbot.db'

def view_all_cases():
    """View all resolution cases"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM resolution_cases ORDER BY id')
    rows = cursor.fetchall()
    conn.close()
    
    print("\n📋 All Resolution Cases:")
    print("=" * 80)
    for row in rows:
        print(f"\nID: {row['id']}")
        print(f"Problem Type: {row['problem_type']}")
        print(f"User Query: {row['user_query']}")
        print(f"Created: {row['created_at']}")
        print("-" * 80)


def update_case_query(case_id, new_query):
    """Update a case's user query"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE resolution_cases
        SET user_query = ?
        WHERE id = ?
    ''', (new_query, case_id))
    
    conn.commit()
    conn.close()
    print(f"✅ Updated case {case_id}")


def delete_case(case_id):
    """Delete a bad case"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM resolution_cases WHERE id = ?', (case_id,))
    
    conn.commit()
    conn.close()
    print(f"✅ Deleted case {case_id}")


if __name__ == '__main__':
    print("🔧 Resolution Cases Manager")
    print("=" * 80)
    
    view_all_cases()
    
    print("\n\nOptions:")
    print("1. Update a case's user query")
    print("2. Delete a case")
    print("3. Exit")
    
    choice = input("\nChoice (1-3): ").strip()
    
    if choice == '1':
        case_id = int(input("Enter case ID to update: "))
        new_query = input("Enter correct user query: ")
        update_case_query(case_id, new_query)
        view_all_cases()
    
    elif choice == '2':
        case_id = int(input("Enter case ID to delete: "))
        confirm = input(f"Delete case {case_id}? (yes/no): ")
        if confirm.lower() == 'yes':
            delete_case(case_id)
            view_all_cases()
    
    print("\n✅ Done!")
