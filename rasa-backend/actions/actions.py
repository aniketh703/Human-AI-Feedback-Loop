from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ConversationPaused
import json
import uuid
from datetime import datetime
import os
import sys

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import save_escalation_to_db

# Import knowledge base for RAG - completely optional
RAG_AVAILABLE = False
get_knowledge_base = None
initialize_knowledge_base = None

# Don't try to import RAG - it causes dependency conflicts with Rasa
# The website_knowledge module requires sentence-transformers which
# conflicts with Rasa's pinned dependencies
print("Note: RAG system disabled to avoid dependency conflicts")

# ============================================================
# CONFIGURATION - Set your website URL here
# ============================================================
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://rasa.com")
# ============================================================

class ActionCheckConfidence(Action):
    """Check confidence and decide if escalation is needed"""
    
    def name(self) -> Text:
        return "action_check_confidence"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get intent confidence
        intent = tracker.latest_message.get('intent', {})
        confidence = intent.get('confidence', 0)
        intent_name = intent.get('name', '')
        
        print(f"Intent: {intent_name}, Confidence: {confidence}")
        
        # Threshold for low confidence
        CONFIDENCE_THRESHOLD = 0.6
        
        if confidence < CONFIDENCE_THRESHOLD:
            dispatcher.utter_message(response="utter_low_confidence")
            return [SlotSet("agent_needed", True)]
        
        return [SlotSet("agent_needed", False)]


class ActionEscalateToAgent(Action):
    """Handle escalation to human agent"""
    
    def name(self) -> Text:
        return "action_escalate_to_agent"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Generate conversation ID
        conversation_id = str(uuid.uuid4())
        
        # Collect conversation history
        conversation_history = []
        for event in tracker.events:
            if event.get('event') == 'user':
                conversation_history.append({
                    'sender': 'user',
                    'text': event.get('text'),
                    'timestamp': event.get('timestamp')
                })
            elif event.get('event') == 'bot':
                conversation_history.append({
                    'sender': 'bot',
                    'text': event.get('text'),
                    'timestamp': event.get('timestamp')
                })
        
        # Save escalation data
        escalation_data = {
            'conversation_id': conversation_id,
            'user_id': tracker.sender_id,
            'timestamp': datetime.now().isoformat(),
            'conversation_history': conversation_history,
            'reason': 'user_request',
            'status': 'pending'
        }
        
        # Save to both file and database
        self.save_escalation(escalation_data)
        save_escalation_to_db(escalation_data)
        
        dispatcher.utter_message(response="utter_transfer_to_agent")
        
        # Send full conversation ID in custom payload
        dispatcher.utter_message(
            text=f"🔄 Connecting you to an agent... (ID: {conversation_id[:8]})",
            json_message={
                "type": "escalation",
                "conversation_id": conversation_id,
                "status": "agent_needed"
            }
        )
        
        return [
            SlotSet("escalated", True),
            SlotSet("conversation_id", conversation_id),
            ConversationPaused()
        ]
    
    def save_escalation(self, data: Dict):
        """Save escalation data to file (backup)"""
        os.makedirs('escalations', exist_ok=True)
        
        filename = f"escalations/{data['conversation_id']}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Escalation saved to file: {filename}")
        except Exception as e:
            print(f"❌ Error saving escalation: {e}")


class ActionLogConversation(Action):
    """Log conversation for training purposes"""
    
    def name(self) -> Text:
        return "action_log_conversation"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Log conversation data
        conversation_log = {
            'user_id': tracker.sender_id,
            'timestamp': datetime.now().isoformat(),
            'latest_message': tracker.latest_message,
            'slots': tracker.current_slot_values()
        }
        
        # Save for future training
        self.save_conversation_log(conversation_log)
        
        return []
    
    def save_conversation_log(self, data: Dict):
        """Save conversation log"""
        os.makedirs('conversation_logs', exist_ok=True)
        
        filename = f"conversation_logs/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{data['user_id']}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Conversation logged: {filename}")
        except Exception as e:
            print(f"❌ Error saving conversation log: {e}")


# ============================================================
# RAG-POWERED ACTIONS - Plug and Play Website Knowledge
# ============================================================

class ActionInitializeKnowledge(Action):
    """Initialize the knowledge base on startup"""
    
    def name(self) -> Text:
        return "action_initialize_knowledge"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        if not RAG_AVAILABLE:
            dispatcher.utter_message(
                text="Knowledge base system is not available. Please install required dependencies."
            )
            return []
        
        try:
            kb = get_knowledge_base(WEBSITE_URL)
            if kb and kb.chunks:
                dispatcher.utter_message(
                    text=f"Knowledge base ready with {len(kb.chunks)} content chunks from {len(kb.visited_urls)} pages."
                )
            else:
                dispatcher.utter_message(
                    text="Knowledge base is being initialized. Please try again in a moment."
                )
        except Exception as e:
            dispatcher.utter_message(
                text=f"Error initializing knowledge base: {str(e)}"
            )
        
        return []


class ActionAnswerFromWebsite(Action):
    """
    RAG Action - Answers questions using website content.
    This is the main plug-and-play action that provides intelligent responses.
    """
    
    def name(self) -> Text:
        return "action_answer_from_website"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        if not RAG_AVAILABLE:
            dispatcher.utter_message(
                text="I'm unable to search the website right now. Let me connect you with a human agent."
            )
            return []
        
        # Get the user's message
        user_message = tracker.latest_message.get('text', '')
        
        if not user_message:
            dispatcher.utter_message(
                text="I didn't catch that. Could you please rephrase your question?"
            )
            return []
        
        try:
            # Get knowledge base
            kb = get_knowledge_base(WEBSITE_URL)
            
            if kb is None or not kb.chunks:
                dispatcher.utter_message(
                    text="I'm still learning about the website. Please try again in a moment, or I can connect you with a human agent."
                )
                return []
            
            # Search for relevant content
            answer = kb.get_answer(user_message, top_k=3)
            
            if answer:
                dispatcher.utter_message(text=answer)
            else:
                dispatcher.utter_message(
                    text="I couldn't find specific information about that on our website. Would you like me to connect you with a human agent who can help?"
                )
                
        except Exception as e:
            dispatcher.utter_message(
                text="I encountered an issue while searching. Let me connect you with someone who can help."
            )
            print(f"Error in ActionAnswerFromWebsite: {e}")
        
        return []


class ActionSmartFallback(Action):
    """
    Smart fallback that tries RAG before giving up.
    Use this as your fallback action.
    """
    
    def name(self) -> Text:
        return "action_smart_fallback"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        user_message = tracker.latest_message.get('text', '')
        intent = tracker.latest_message.get('intent', {})
        confidence = intent.get('confidence', 0)
        
        print(f"[SmartFallback] User message: {user_message}")
        print(f"[SmartFallback] RAG_AVAILABLE: {RAG_AVAILABLE}")
        print(f"[SmartFallback] WEBSITE_URL: {WEBSITE_URL}")
        
        # Try to answer from website knowledge base
        if RAG_AVAILABLE:
            try:
                kb = get_knowledge_base(WEBSITE_URL)
                print(f"[SmartFallback] KB loaded: {kb is not None}, chunks: {len(kb.chunks) if kb else 0}")
                
                if kb and kb.chunks:
                    answer = kb.get_answer(user_message, top_k=3)
                    
                    if answer:
                        dispatcher.utter_message(
                            text=f"I found this information that might help:\n\n{answer}"
                        )
                        return []
            except Exception as e:
                print(f"Error in smart fallback RAG: {e}")
        
        # If RAG didn't help, provide a friendly fallback
        dispatcher.utter_message(
            text="I'm not sure I understand. Here's what I can help with:\n\n"
                 "• Password reset and account issues\n"
                 "• Billing and pricing questions\n"
                 "• Technical support\n"
                 "• Product information\n"
                 "• Installation help\n\n"
                 "Or I can connect you with a human agent. What would you prefer?"
        )
        
        return []


class ActionSearchWebsite(Action):
    """
    Explicit website search action.
    Users can ask to search the website specifically.
    """
    
    def name(self) -> Text:
        return "action_search_website"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        if not RAG_AVAILABLE:
            dispatcher.utter_message(
                text="Search is not available right now. Please try again later."
            )
            return []
        
        # Get search query from slot or message
        search_query = tracker.get_slot('search_query')
        
        if not search_query:
            # Extract from latest message
            search_query = tracker.latest_message.get('text', '')
            # Remove common prefixes
            for prefix in ['search for', 'find', 'look up', 'search']:
                if search_query.lower().startswith(prefix):
                    search_query = search_query[len(prefix):].strip()
        
        if not search_query:
            dispatcher.utter_message(
                text="What would you like me to search for on our website?"
            )
            return []
        
        try:
            kb = get_knowledge_base(WEBSITE_URL)
            
            if kb and kb.chunks:
                results = kb.search(search_query, top_k=5)
                
                if results:
                    response = f"Here's what I found for '{search_query}':\n\n"
                    
                    for i, result in enumerate(results[:3], 1):
                        response += f"{i}. **{result['title']}**\n"
                        response += f"   {result['text'][:150]}...\n"
                        response += f"   🔗 {result['url']}\n\n"
                    
                    dispatcher.utter_message(text=response)
                else:
                    dispatcher.utter_message(
                        text=f"I couldn't find anything matching '{search_query}' on our website. Try different keywords or ask me a question!"
                    )
            else:
                dispatcher.utter_message(
                    text="The search feature is still initializing. Please try again shortly."
                )
                
        except Exception as e:
            dispatcher.utter_message(
                text="I encountered an issue while searching. Please try again."
            )
            print(f"Error in ActionSearchWebsite: {e}")
        
        return [SlotSet('search_query', None)]


class ActionRefreshKnowledge(Action):
    """
    Refresh the knowledge base by re-crawling the website.
    Useful when website content has been updated.
    """
    
    def name(self) -> Text:
        return "action_refresh_knowledge"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        if not RAG_AVAILABLE:
            dispatcher.utter_message(
                text="Knowledge base system is not available."
            )
            return []
        
        dispatcher.utter_message(
            text="Refreshing knowledge base... This may take a few minutes."
        )
        
        try:
            kb = initialize_knowledge_base(WEBSITE_URL, force_refresh=True)
            
            dispatcher.utter_message(
                text=f"✅ Knowledge base refreshed! Now containing {len(kb.chunks)} content chunks from {len(kb.visited_urls)} pages."
            )
        except Exception as e:
            dispatcher.utter_message(
                text=f"Error refreshing knowledge base: {str(e)}"
            )
        
        return []


class ActionDefaultFallback(Action):
    """Default fallback action - now uses smart fallback with RAG"""
    
    def name(self) -> Text:
        return "action_default_fallback"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Delegate to smart fallback
        smart_fallback = ActionSmartFallback()
        return smart_fallback.run(dispatcher, tracker, domain)