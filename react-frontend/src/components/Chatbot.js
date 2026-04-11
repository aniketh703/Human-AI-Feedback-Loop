import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import './Chatbot.css';

// Generate or retrieve unique user ID
const getOrCreateUserId = () => {
  let userId = localStorage.getItem('chatbot_user_id');
  if (!userId) {
    userId = 'user_' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('chatbot_user_id', userId);
  }
  return userId;
};

const Chatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [agentConnected, setAgentConnected] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connected');
  const [showToast, setShowToast] = useState({ visible: false, message: '', type: 'info' });
  const displayedMessageIdsRef = useRef(new Set());
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const RASA_URL = process.env.REACT_APP_RASA_URL || 'http://localhost:5005/webhooks/rest/webhook';
  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api';
  const USER_ID = getOrCreateUserId();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  // Load messages from localStorage on mount
  useEffect(() => {
    const savedMessages = localStorage.getItem('chatbot_messages');
    const savedConversationId = localStorage.getItem('chatbot_conversation_id');
    const savedAgentConnected = localStorage.getItem('chatbot_agent_connected');
    
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch (e) {
        console.error('Error loading saved messages:', e);
      }
    }
    if (savedConversationId) setConversationId(savedConversationId);
    if (savedAgentConnected === 'true') setAgentConnected(true);
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('chatbot_messages', JSON.stringify(messages));
    }
    if (conversationId) {
      localStorage.setItem('chatbot_conversation_id', conversationId);
    }
    localStorage.setItem('chatbot_agent_connected', agentConnected.toString());
  }, [messages, conversationId, agentConnected]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Check connection status periodically
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await axios.get(`${API_URL}/health`, { timeout: 3000 });
        setConnectionStatus('connected');
      } catch (error) {
        setConnectionStatus('disconnected');
      }
    };
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, [API_URL]);

  // Toast notification helper
  const showToastMessage = (message, type = 'info') => {
    setShowToast({ visible: true, message, type });
    setTimeout(() => setShowToast({ visible: false, message: '', type: 'info' }), 3000);
  };

  // Clear chat history
  const clearChat = async () => {
    if (window.confirm('Are you sure you want to clear the chat history?')) {
      // Reset Rasa conversation tracker
      try {
        await axios.post(`http://localhost:5005/conversations/${USER_ID}/tracker/events`, {
          event: 'restart'
        });
      } catch (e) {
        console.log('Could not reset Rasa tracker:', e);
      }
      
      setMessages([]);
      setConversationId(null);
      setAgentConnected(false);
      displayedMessageIdsRef.current = new Set();
      localStorage.removeItem('chatbot_messages');
      localStorage.removeItem('chatbot_conversation_id');
      localStorage.removeItem('chatbot_agent_connected');
      showToastMessage('Chat cleared', 'success');
    }
  };

  const fetchAgentMessages = useCallback(async () => {
    if (!conversationId) return;

    try {
      const response = await axios.get(
        `${API_URL}/user/${USER_ID}/messages?conversation_id=${conversationId}`
      );

      if (response.data.success && response.data.messages.length > 0) {
        const agentMessages = response.data.messages;
        
        agentMessages.forEach(msg => {
          // Check if we've already displayed this message using ref
          if (!displayedMessageIdsRef.current.has(msg.id)) {
            setMessages(prev => [...prev, {
              sender: 'agent',
              text: msg.message,
              id: msg.id,
              timestamp: new Date().toISOString()
            }]);
            
            displayedMessageIdsRef.current.add(msg.id);
          }
        });
      }
    } catch (error) {
      console.error('Error fetching agent messages:', error);
    }
  }, [conversationId, API_URL, USER_ID]);

  // Poll for agent messages when agent is connected
  useEffect(() => {
    if (agentConnected && conversationId) {
      const interval = setInterval(() => {
        fetchAgentMessages();
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }
  }, [agentConnected, conversationId, fetchAgentMessages]);

  // Handle quick reply button click
  const handleQuickReply = (payload) => {
    setInput(payload);
    // Trigger send after setting input
    setTimeout(() => {
      const fakeEvent = { preventDefault: () => {} };
      sendMessage(fakeEvent, payload);
    }, 100);
  };

  // Submit feedback for a message
  const submitFeedback = async (messageIndex, rating) => {
    try {
      const message = messages[messageIndex];
      await axios.post(`${API_URL}/feedback`, {
        user_id: USER_ID,
        message_text: message.text,
        rating: rating,
        conversation_id: conversationId,
        intent: message.intent || 'unknown'
      });
      
      // Update message to show feedback was submitted
      setMessages(prev => prev.map((msg, idx) => 
        idx === messageIndex ? { ...msg, feedbackGiven: rating } : msg
      ));
      showToastMessage('Thanks for your feedback!', 'success');
    } catch (error) {
      console.error('Error submitting feedback:', error);
      showToastMessage('Failed to submit feedback', 'error');
    }
  };

  const sendMessage = async (e, quickReplyText = null) => {
    e.preventDefault();
    const messageText = quickReplyText || input;
    if (!messageText.trim()) return;

    const userMessage = { 
      sender: 'user', 
      text: messageText,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    if (!quickReplyText) setInput('');
    setIsSending(true);

    // If agent is connected, send to backend so agent can see it
    if (agentConnected && conversationId) {
      try {
        await axios.post(`${API_URL}/escalations/${conversationId}/user-message`, {
          user_id: USER_ID,
          message: messageText
        });
      } catch (error) {
        console.error('Error sending user message to agent:', error);
        showToastMessage('Failed to send message', 'error');
      }
      setIsSending(false);
      return;
    }

    setIsTyping(true);

    try {
      console.log('Sending message to Rasa:', RASA_URL, { sender: USER_ID, message: messageText });
      const response = await axios.post(RASA_URL, {
        sender: USER_ID,
        message: messageText
      });

      console.log('Rasa response:', response.data);
      setIsTyping(false);

      if (response.data && response.data.length > 0) {
        const botMessages = response.data.map(msg => ({
          sender: 'bot',
          text: msg.text,
          image: msg.image || null,
          buttons: msg.buttons || null,
          timestamp: new Date().toISOString(),
          intent: msg.intent || null
        }));

        setMessages(prev => [...prev, ...botMessages]);

        // Check if escalation occurred
        const hasEscalation = botMessages.some(m => 
          m.text && m.text.includes('Connecting you to an agent')
        );

        if (hasEscalation) {
          setAgentConnected(true);
          
          // Get the conversation ID from the latest escalation
          setTimeout(async () => {
            try {
              const escalationResponse = await axios.get(
                `${API_URL}/escalations/by-user/${USER_ID}/latest`
              );
              
              if (escalationResponse.data.success) {
                setConversationId(escalationResponse.data.conversation_id);
                setMessages(prev => [...prev, {
                  sender: 'system',
                  text: '👤 An agent will be with you shortly...',
                  timestamp: new Date().toISOString()
                }]);
              }
            } catch (error) {
              console.error('Error getting conversation ID:', error);
            }
          }, 1000);
        }
      } else {
        // Empty response from Rasa
        console.warn('Empty response from Rasa');
        setMessages(prev => [...prev, {
          sender: 'bot',
          text: "I'm sorry, I didn't understand that. Could you rephrase?",
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setIsTyping(false);
      setConnectionStatus('disconnected');
      setMessages(prev => [...prev, {
        sender: 'bot',
        text: 'Sorry, I am having trouble connecting. Please try again.',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsSending(false);
    }
  };

  // Format timestamp for display
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="chatbot-container">
      {/* Toast Notification */}
      {showToast.visible && (
        <div className={`toast toast-${showToast.type}`}>
          {showToast.message}
        </div>
      )}

      <button 
        className="chat-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
      >
        {isOpen ? '✕' : '💬'}
      </button>

      {isOpen && (
        <div className="chat-window" role="dialog" aria-label="Chat window">
          <div className="chat-header">
            <div className="header-left">
              <h3>Chatbot</h3>
              {connectionStatus === 'disconnected' && (
                <span className="connection-status disconnected">⚠️ Offline</span>
              )}
            </div>
            <div className="header-right">
              {agentConnected && (
                <span className="agent-status">🟢 Agent Connected</span>
              )}
              <button 
                className="clear-chat-btn" 
                onClick={clearChat}
                title="Clear chat history"
                aria-label="Clear chat history"
              >
                🗑️
              </button>
            </div>
          </div>

          <div className="messages-container" role="log" aria-live="polite">
            {messages.length === 0 && (
              <div className="welcome-message">
                <p>👋 Hi! How can I help you today?</p>
                <div className="quick-start-buttons">
                  <button onClick={() => handleQuickReply('I have a technical issue')}>🔧 Technical Issue</button>
                  <button onClick={() => handleQuickReply('I have a billing question')}>💳 Billing Question</button>
                  <button onClick={() => handleQuickReply('I need to talk to an agent')}>👤 Talk to Agent</button>
                </div>
              </div>
            )}
            
            {messages.map((msg, index) => (
              <div 
                key={`${msg.sender}-${index}-${msg.id || ''}`}
                className={`message ${msg.sender} ${msg.isError ? 'error' : ''}`}
              >
                {msg.sender === 'agent' && (
                  <div className="agent-badge">👤 Agent</div>
                )}
                
                {/* Message Text */}
                <div className="message-content">{msg.text}</div>
                
                {/* Image Support */}
                {msg.image && (
                  <div className="message-image-container">
                    <img 
                      src={msg.image} 
                      alt="Help illustration" 
                      className="message-image"
                      onClick={() => window.open(msg.image, '_blank')}
                    />
                  </div>
                )}
                
                {/* Quick Reply Buttons */}
                {msg.buttons && msg.buttons.length > 0 && (
                  <div className="quick-reply-buttons">
                    {msg.buttons.map((btn, btnIdx) => (
                      <button
                        key={btnIdx}
                        className="quick-reply-btn"
                        onClick={() => handleQuickReply(btn.payload || btn.title)}
                      >
                        {btn.title}
                      </button>
                    ))}
                  </div>
                )}
                
                {/* Timestamp */}
                {msg.timestamp && (
                  <div className="message-time">{formatTime(msg.timestamp)}</div>
                )}
                
                {/* Feedback Buttons for Bot Messages */}
                {msg.sender === 'bot' && !msg.isError && !msg.feedbackGiven && (
                  <div className="feedback-buttons">
                    <span className="feedback-label">Was this helpful?</span>
                    <button 
                      onClick={() => submitFeedback(index, 1)} 
                      className="feedback-btn thumbs-up"
                      aria-label="Yes, this was helpful"
                    >
                      👍
                    </button>
                    <button 
                      onClick={() => submitFeedback(index, 0)} 
                      className="feedback-btn thumbs-down"
                      aria-label="No, this was not helpful"
                    >
                      👎
                    </button>
                  </div>
                )}
                
                {/* Feedback Given Indicator */}
                {msg.feedbackGiven !== undefined && (
                  <div className="feedback-given">
                    {msg.feedbackGiven === 1 ? '✅ Thanks!' : '📝 Thanks for feedback'}
                  </div>
                )}
              </div>
            ))}
            
            {/* Typing Indicator */}
            {isTyping && (
              <div className="message bot typing-indicator">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={sendMessage} className="input-container">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={agentConnected ? "Reply to agent..." : "Type a message..."}
              disabled={isSending || connectionStatus === 'disconnected'}
              aria-label="Type your message"
            />
            <button 
              type="submit" 
              disabled={isSending || !input.trim() || connectionStatus === 'disconnected'}
              aria-label="Send message"
            >
              {isSending ? '⏳' : '📤'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

export default Chatbot;
