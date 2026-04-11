import subprocess
import time
from datetime import datetime
import sqlite3

DB_PATH = 'chatbot.db'

def count_new_resolutions(last_check_time):
    """Count resolutions since last check"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM resolution_cases
            WHERE created_at > ?
        ''', (last_check_time,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    except sqlite3.Error as e:
        print(f"❌ Database error in count_new_resolutions: {e}")
        return 0
    except Exception as e:
        print(f"❌ Unexpected error in count_new_resolutions: {e}")
        return 0


def retrain_model():
    """Retrain the Rasa model"""
    print(f"\n🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting retraining...")
    
    try:
        # Run training data generator
        print("📊 Generating training data from resolutions...")
        subprocess.run(['python', 'train_from_resolutions.py'], check=True, input=b'yes\n')
        
        # Train Rasa model
        print("\n🤖 Training Rasa model...")
        subprocess.run(['rasa', 'train'], check=True)
        
        print(f"✅ Retraining completed at {datetime.now().strftime('%H:%M:%S')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Retraining failed: {e}")
        return False


def monitor_and_retrain(check_interval=300, min_new_cases=3):
    """
    Monitor for new resolutions and retrain when threshold is met
    
    Args:
        check_interval: Seconds between checks (default 300 = 5 minutes)
        min_new_cases: Minimum new cases before retraining (default 3)
    """
    print("\n🤖 Auto-Retrain Monitor Started")
    print("=" * 50)
    print(f"   Check Interval: {check_interval}s ({check_interval//60} minutes)")
    print(f"   Min Cases for Retrain: {min_new_cases}")
    print("=" * 50)
    
    last_check = datetime.now().isoformat()
    
    try:
        while True:
            time.sleep(check_interval)
            
            new_cases = count_new_resolutions(last_check)
            
            if new_cases > 0:
                print(f"\n📊 Found {new_cases} new resolution(s)")
            
            if new_cases >= min_new_cases:
                print(f"🎯 Threshold reached! Retraining model...")
                
                success = retrain_model()
                
                if success:
                    last_check = datetime.now().isoformat()
                    print(f"\n✅ Model updated! Next check in {check_interval//60} minutes")
                else:
                    print(f"\n⚠️ Retrain failed, will try again next check")
            else:
                print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] Waiting... ({new_cases}/{min_new_cases} cases)")
    
    except KeyboardInterrupt:
        print("\n\n👋 Auto-retrain monitor stopped")


if __name__ == '__main__':
    import sys
    
    # Get parameters from command line or use defaults
    check_interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300  # 5 minutes
    min_cases = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    monitor_and_retrain(check_interval, min_cases)
