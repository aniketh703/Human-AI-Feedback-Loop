import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Chatbot from './components/Chatbot';
import AgentDashboard from './components/AgentDashboard';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* User Chat Interface */}
          <Route path="/" element={
            <>
              <header className="App-header">
                <h1>My Chatbot Application</h1>
                <p>Chat with our bot using the button in the bottom-right corner!</p>
                <Link to="/agent" className="agent-link">
                  🎧 Agent Dashboard
                </Link>
              </header>
              <Chatbot />
            </>
          } />
          
          {/* Agent Dashboard */}
          <Route path="/agent" element={<AgentDashboard />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
