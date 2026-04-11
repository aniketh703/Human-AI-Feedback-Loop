import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './AgentDashboard.css';

// Canned responses for quick replies
const CANNED_RESPONSES = [
  { label: '👋 Greeting', text: 'Hello! I\'m here to help. Let me look into this for you.' },
  { label: '⏳ Working on it', text: 'I\'m looking into this right now. Please give me a moment.' },
  { label: '✅ Resolved', text: 'I\'ve resolved the issue. Is there anything else I can help with?' },
  { label: '📧 Follow up', text: 'I\'ll follow up via email with more details. You should receive it within 24 hours.' },
  { label: '🔄 Restart', text: 'Please try restarting your application/browser and let me know if the issue persists.' },
  { label: '🔗 Password Reset', text: 'I\'ve sent a password reset link to your email. Please check your inbox and spam folder.' },
];

const AgentDashboard = () => {
  const [escalations, setEscalations] = useState([]);
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [agentMessage, setAgentMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [problemType, setProblemType] = useState('general');
  const [resolutionSteps, setResolutionSteps] = useState('');
  const [userQuery, setUserQuery] = useState('');
  const [feedbackStats, setFeedbackStats] = useState(null);
  const [showStats, setShowStats] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [showToast, setShowToast] = useState({ visible: false, message: '', type: 'info' });
  
  // Use ref to track selected conversation ID for polling
  const selectedConversationIdRef = useRef(null);
  const previousEscalationCount = useRef(0);
  const notificationSound = useRef(null);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api';
  const AGENT_ID = 'agent_001';

  // Initialize notification sound
  useEffect(() => {
    notificationSound.current = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp6Whn94dnV+i5yamId8dXR4g5GdnZSHfHZ1eIKPm5qThXt1dXmEkpuZkIR6dXZ7h5Wbl46DeHV2fIqYm5eLgXd1d32MmpuXiX93dXd/jpualod+dnV4gZGcm5SDfHV1eYOTnJmSgnp0dXqGlpuYj4B5dHV7iJibl4x/d3R2fYuam5aJfXZ0d3+Nnp2UiHx2dXeBkJ2dlYZ7dXV4gpKdnJOEenR1eoWVnJqRgXl0dXuHl5uYjoB4dHV8iZqblot+d3R2foybnJiJfHZ0d3+PnZ2Vh3t1dXiBkp6dlIV6dHV5hJadm5KCeXR0e4aYnJmPgHh0dHyJmpuXjH53dHZ9jJucl4l8dnR3f4+enZaHenV0eIGSnp2UhXl0dXmFlp2bkoF4dHR7h5mcmI+AeHR0fIqbnJaLfnd0dn2Nm5yYiXx2dHd/kJ6dlod6dXR4gZOfnZWFenR0eYSXnpuSgnl0dHuHmZyZj4B4dHR8ipublot+d3R2fY2cnJiJfHZ0d3+QoJ6Wh3p0dHiBk5+dlYV5dHR5hZienZKCeHR0e4eZnZmPgHh0dHyLnJ2Xi353dXZ+jp2dl4l8dnR3gJGfnpaGenV0eIKUn52VhXl0dXmGmZ6ckoF4dHR7iJqcmI9/d3R0fIudnZeLfnd0dn6OnZ2XiXx2dHd/kaCelod6dXR4gpWgnZWFenR1eYaZnpySgXh0dHuIm52Yj393dHR8i52cl4t+d3R2fo6enZiJfHZ0d4CRoJ6Wh3p1dHiClaCdlYV5dHV5hpqenpKBeHR0e4mbnZiPf3d0dHyLnp2Xi353dHZ+jp6dl4l8dnR3gJKgn5aHenV0eIKWoJ2VhXl0dXmHmp6ekoF4dHR7iZydmI9/d3R0fIyenZeLfnd0dn+Pnp2YiXx2dHeBk6CflYd6dXR4g5agnZWFeXR1eYecnp6SgXh0dHuKnZ2Yj393dHR8jJ+dl4t+d3R2f4+fnpiJfHZ0d4GTn5+Wh3p1dHiDlqCdlYV5dHR5h5yenpKBeHR0e4qenZiPf3d0dHyNn52Xi393dXZ/kJ+emIl8dnR3gZSgn5aHenV0eISXoJ2VhXl0dHmInZ6ekoF4dHR7i56dmI9/d3R0fI2gn5eLf3d1dn+Qn56YiXx2dHeBlaCflod6dXR4hJigDnZVhXl0dHmJnp6dkoF3c3R7i5+fmI9/d3Rzd42gn5eLf3Z0dn+Rn5+YiXx1dXeClqCflYd6dXR4hZignZWFeHRzeYmdnp2SgXdzdHuMn5+Yj392c3R8jqGfl4t+dnR1gJKgn5iJfHV0d4OXoJ6Vh3l0dHiGmp+dlYR4dHR5ip6enJKAd3N0e42fn5iPfnZzdH2PoaCXi351dHaBk6CfmIl7dXR3g5igz5WHend0eIaboJ2UhHh0dHmKn56ckn93c3R8jqCfl4t9dnR1gJOgoJiJfHV0eISYoJ6Uh3l0dHiHm6CdlIR4dHR5iqCenJJ/d3N0fI+hoJeLfXZ0dYGUoKCYiXx1dXeEmqDelId5dHR4h5ygnZSEeHR0eYugnpySf3dzdHyPoaCXi311dHWBlaCgmIl8dXV3hJqg3pSHeXR0eIecn52UhHh0dHmLoJ6ckn93c3R8kKGgl4t9dXR1gpWgoJiJe3V1d4WaoN6Uh3l0dHiInJ+dlIR3dHR5i6GenJJ/d3N0fJChoJeLfXV0dYKWoKCYiXx1dXeFm6DelId5dHR4iJyf');
  }, []);

  // Show toast notification
  const showToastMessage = (message, type = 'info') => {
    setShowToast({ visible: true, message, type });
    setTimeout(() => setShowToast({ visible: false, message: '', type: 'info' }), 3000);
  };

  // Play notification sound
  const playNotificationSound = useCallback(() => {
    if (soundEnabled && notificationSound.current) {
      notificationSound.current.play().catch(e => console.log('Sound play failed:', e));
    }
  }, [soundEnabled]);

  // Update ref when selectedEscalation changes
  useEffect(() => {
    selectedConversationIdRef.current = selectedEscalation?.conversation_id || null;
  }, [selectedEscalation?.conversation_id]);

  // Refresh selected escalation without changing selection state
  const refreshSelectedEscalation = useCallback(async () => {
    const conversationId = selectedConversationIdRef.current;
    if (!conversationId) return;
    try {
      const response = await axios.get(
        `${API_URL}/escalations/${conversationId}`
      );
      if (response.data.success) {
        setSelectedEscalation(response.data.escalation);
      }
    } catch (error) {
      console.error('Error refreshing escalation:', error);
    }
  }, [API_URL]);

  // Fetch feedback stats
  const fetchFeedbackStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/feedback/stats`);
      if (response.data.success) {
        setFeedbackStats(response.data.stats);
      }
    } catch (error) {
      console.error('Error fetching feedback stats:', error);
    }
  }, [API_URL]);

  useEffect(() => {
    fetchPendingEscalations();
    fetchFeedbackStats();
    const interval = setInterval(fetchPendingEscalations, 5000);
    const statsInterval = setInterval(fetchFeedbackStats, 30000);
    return () => {
      clearInterval(interval);
      clearInterval(statsInterval);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll for updates on selected escalation (real-time message updates)
  useEffect(() => {
    // Only poll if there's a selected conversation
    if (!selectedConversationIdRef.current) return;
    
    const messageInterval = setInterval(() => {
      refreshSelectedEscalation();
    }, 3000);
    return () => clearInterval(messageInterval);
  }, [selectedEscalation?.conversation_id, refreshSelectedEscalation]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchPendingEscalations = async () => {
    try {
      const response = await axios.get(`${API_URL}/escalations/pending`);
      if (response.data.success) {
        const newEscalations = response.data.escalations;
        
        // Check for new escalations and play sound
        if (newEscalations.length > previousEscalationCount.current) {
          playNotificationSound();
          showToastMessage(`🔔 New escalation received!`, 'info');
        }
        previousEscalationCount.current = newEscalations.length;
        
        setEscalations(newEscalations);
      }
    } catch (error) {
      console.error('Error fetching escalations:', error);
    }
  };

  // Calculate priority based on wait time
  const getPriority = (createdAt) => {
    const waitMinutes = (Date.now() - new Date(createdAt).getTime()) / 60000;
    if (waitMinutes > 10) return { label: 'HIGH', class: 'priority-high' };
    if (waitMinutes > 5) return { label: 'MED', class: 'priority-medium' };
    return { label: 'LOW', class: 'priority-low' };
  };

  // Insert canned response
  const insertCannedResponse = (text) => {
    setAgentMessage(prev => prev ? `${prev}\n\n${text}` : text);
  };

  const selectEscalation = async (escalation) => {
    try {
      const response = await axios.get(
        `${API_URL}/escalations/${escalation.conversation_id}`
      );
      if (response.data.success) {
        setSelectedEscalation(response.data.escalation);
        
        // Auto-detect the real user query (not escalation request)
        const escalationKeywords = ['agent', 'human', 'representative', 'speak to', 'talk to'];
        let detectedQuery = '';
        
        if (response.data.escalation.conversation_history) {
          for (const msg of response.data.escalation.conversation_history) {
            if (msg.sender === 'user') {
              const text = msg.text.toLowerCase();
              const isEscalation = escalationKeywords.some(kw => text.includes(kw));
              
              if (!isEscalation) {
                detectedQuery = msg.text;
                break;
              }
            }
          }
        }
        
        setUserQuery(detectedQuery);  // Auto-populate
      }
    } catch (error) {
      console.error('Error fetching escalation details:', error);
    }
  };

  const sendAgentMessage = async (e) => {
    e.preventDefault();
    if (!agentMessage.trim() || !selectedEscalation) return;

    setLoading(true);
    try {
      const response = await axios.post(
        `${API_URL}/escalations/${selectedEscalation.conversation_id}/respond`,
        {
          agent_id: AGENT_ID,
          message: agentMessage
        }
      );

      if (response.data.success) {
        setAgentMessage('');
        showToastMessage('Message sent!', 'success');
        selectEscalation(selectedEscalation);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      showToastMessage('Failed to send message', 'error');
    } finally {
      setLoading(false);
    }
  };

  const resolveCase = async () => {
    if (!selectedEscalation) return;

    const steps = resolutionSteps.split('\n').filter(s => s.trim());
    
    if (!userQuery.trim()) {
      showToastMessage('Please provide the original user query', 'error');
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(
        `${API_URL}/escalations/${selectedEscalation.conversation_id}/resolve`,
        {
          agent_id: AGENT_ID,
          problem_type: problemType,
          user_query: userQuery,
          resolution_data: {
            steps: steps,
            intent: problemType,
            entities: []
          }
        }
      );

      if (response.data.success) {
        showToastMessage('Case resolved and saved for AI training!', 'success');
        setSelectedEscalation(null);
        setResolutionSteps('');
        setUserQuery('');
        setProblemType('general');
        fetchPendingEscalations();
      }
    } catch (error) {
      console.error('Error resolving case:', error);
      showToastMessage('Failed to resolve case', 'error');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="dashboard-container">
      {/* Toast Notification */}
      {showToast.visible && (
        <div className={`dashboard-toast toast-${showToast.type}`}>
          {showToast.message}
        </div>
      )}

      <div className="dashboard-header">
        <h1 className="dashboard-title">🎧 Agent Dashboard</h1>
        <div className="header-controls">
          <button 
            className={`sound-toggle ${soundEnabled ? 'enabled' : 'disabled'}`}
            onClick={() => setSoundEnabled(!soundEnabled)}
            title={soundEnabled ? 'Disable notifications' : 'Enable notifications'}
          >
            {soundEnabled ? '🔔' : '🔕'}
          </button>
          <button 
            className="stats-toggle"
            onClick={() => setShowStats(!showStats)}
          >
            📊 Stats
          </button>
          <div className="badge">
            {escalations.length} Pending Cases
          </div>
        </div>
      </div>

      {/* Feedback Stats Panel */}
      {showStats && feedbackStats && (
        <div className="stats-panel">
          <h3>📊 Feedback Analytics</h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{feedbackStats.total}</div>
              <div className="stat-label">Total Feedback</div>
            </div>
            <div className="stat-card positive">
              <div className="stat-value">{feedbackStats.positive}</div>
              <div className="stat-label">👍 Positive</div>
            </div>
            <div className="stat-card negative">
              <div className="stat-value">{feedbackStats.negative}</div>
              <div className="stat-label">👎 Negative</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{feedbackStats.satisfaction_rate.toFixed(1)}%</div>
              <div className="stat-label">Satisfaction Rate</div>
            </div>
          </div>
          {feedbackStats.by_intent && feedbackStats.by_intent.length > 0 && (
            <div className="intent-breakdown">
              <h4>Feedback by Intent (lowest rated first)</h4>
              <div className="intent-list">
                {feedbackStats.by_intent.map((item, idx) => (
                  <div key={idx} className="intent-item">
                    <span className="intent-name">{item.intent}</span>
                    <span className="intent-count">{item.count} ratings</span>
                    <span className={`intent-rating ${item.avg_rating >= 0.5 ? 'good' : 'bad'}`}>
                      {(item.avg_rating * 100).toFixed(0)}% positive
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="dashboard-content">
        {/* Left Panel - Escalation List */}
        <div className="left-panel">
          <h2 className="panel-title">Pending Escalations</h2>
          
          {escalations.length === 0 ? (
            <div className="empty-state">
              <p>✅ No pending escalations</p>
              <p className="empty-subtext">Great job! All cases handled.</p>
            </div>
          ) : (
            <div className="escalation-list">
              {escalations.map((esc) => {
                const priority = getPriority(esc.created_at);
                return (
                  <div
                    key={esc.conversation_id}
                    className={`escalation-card ${
                      selectedEscalation?.conversation_id === esc.conversation_id
                        ? 'active'
                        : ''
                    }`}
                    onClick={() => selectEscalation(esc)}
                  >
                    <div className="escalation-header-row">
                      <span className="user-id">User: {esc.user_id}</span>
                      <span className={`priority-badge ${priority.class}`}>
                        {priority.label}
                      </span>
                    </div>
                    <div className="escalation-meta">
                      <span className="reason">📋 {esc.reason}</span>
                      <span className="timestamp-small">
                        {formatTimestamp(esc.created_at)}
                      </span>
                    </div>
                    <div className="message-preview">
                      {esc.conversation_history?.[0]?.text || 'No messages'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Panel - Conversation View */}
        <div className="right-panel">
          {selectedEscalation ? (
            <>
              <div className="conversation-header">
                <div>
                  <h2 className="conversation-title">
                    Conversation Details
                  </h2>
                  <p className="conv-id-full">
                    ID: {selectedEscalation.conversation_id}
                  </p>
                </div>
                <span className="status-badge">
                  {selectedEscalation.status}
                </span>
              </div>

              {/* Conversation History */}
              <div className="messages-container-agent">
                <h3 className="section-title">Conversation History</h3>
                {selectedEscalation.conversation_history?.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`msg ${msg.sender === 'user' ? 'user-msg' : 'bot-msg'}`}
                  >
                    <div className="msg-sender">
                      {msg.sender === 'user' ? '👤 User' : '🤖 Bot'}
                    </div>
                    <div className="msg-text">{msg.text}</div>
                    <div className="msg-time">
                      {formatTimestamp(msg.timestamp)}
                    </div>
                  </div>
                ))}

                {/* Agent Responses */}
                {selectedEscalation.agent_responses?.map((resp, idx) => (
                  <div key={`agent-${idx}`} className="msg agent-msg">
                    <div className="msg-sender">🎧 Agent</div>
                    <div className="msg-text">{resp.message}</div>
                    <div className="msg-time">
                      {formatTimestamp(resp.timestamp)}
                    </div>
                  </div>
                ))}
              </div>

              {/* Agent Response Form */}
              <div className="response-section">
                <h3 className="section-title">Send Response</h3>
                
                {/* Canned Responses */}
                <div className="canned-responses">
                  <span className="canned-label">Quick replies:</span>
                  <div className="canned-buttons">
                    {CANNED_RESPONSES.map((resp, idx) => (
                      <button
                        key={idx}
                        className="canned-btn"
                        onClick={() => insertCannedResponse(resp.text)}
                        title={resp.text}
                      >
                        {resp.label}
                      </button>
                    ))}
                  </div>
                </div>
                
                <form onSubmit={sendAgentMessage} className="response-form">
                  <textarea
                    value={agentMessage}
                    onChange={(e) => setAgentMessage(e.target.value)}
                    placeholder="Type your response to the user..."
                    className="response-textarea"
                    rows={3}
                  />
                  <button
                    type="submit"
                    disabled={loading || !agentMessage.trim()}
                    className="send-btn"
                  >
                    {loading ? '⏳ Sending...' : '📤 Send Response'}
                  </button>
                </form>
              </div>

              {/* Resolution Section */}
              <div className="resolution-section">
                <h3 className="section-title">Resolve & Train AI</h3>
                
                <div className="form-group">
                  <label className="form-label">
                    Original User Query: <span style={{color: 'red'}}>*</span>
                  </label>
                  <input
                    type="text"
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    placeholder="What did the user originally ask? (e.g., How to clear browser cache)"
                    className="form-select"
                  />
                  <p style={{fontSize: '12px', color: '#7f8c8d', marginTop: '5px'}}>
                    ℹ️ Enter the actual problem, not "I want to talk to an agent"
                  </p>
                </div>

                <div className="form-group">
                  <label className="form-label">Problem Type:</label>
                  <select
                    value={problemType}
                    onChange={(e) => setProblemType(e.target.value)}
                    className="form-select"
                  >
                    <option value="general">General Inquiry</option>
                    <option value="technical_issue">Technical Issue</option>
                    <option value="billing_issue">Billing Issue</option>
                    <option value="account_issue">Account Issue</option>
                    <option value="feature_request">Feature Request</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Resolution Steps (one per line):
                  </label>
                  <textarea
                    value={resolutionSteps}
                    onChange={(e) => setResolutionSteps(e.target.value)}
                    placeholder="Step 1: Checked user account status&#10;Step 2: Reset password&#10;Step 3: Verified access restored"
                    className="response-textarea"
                    rows={4}
                  />
                </div>

                <button
                  onClick={resolveCase}
                  disabled={loading || !resolutionSteps.trim() || !userQuery.trim()}
                  className="resolve-btn"
                >
                  {loading ? '⏳ Resolving...' : '✅ Mark Resolved & Save for Training'}
                </button>
                
                <p className="help-text">
                  💡 This will save the resolution as training data for the AI
                </p>
              </div>
            </>
          ) : (
            <div className="empty-selection">
              <h2 className="empty-selection-title">
                👈 Select an escalation to view details
              </h2>
              <p className="empty-selection-text">
                Click on any pending case from the list to start helping the user
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentDashboard;
