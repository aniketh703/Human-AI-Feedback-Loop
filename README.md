# Human-AI Feedback Loop

A full-stack customer-support chatbot platform that combines **Rasa automation** with **human agent escalation** and a **learning feedback loop**.

When the bot cannot confidently answer (or the user asks for a human), the conversation is escalated to an agent dashboard. Agents respond live, resolve the case, and the resolution is stored as structured data that can be reused for future model improvement.

---

## What this project is

This repository contains two main applications:

- **`rasa-backend/`**: Rasa assistant, custom action server, Flask API, SQLite data layer, and training/automation utilities.
- **`react-frontend/`**: React UI containing:
  - a user-facing chatbot widget
  - an agent dashboard for handling escalations and collecting resolution data.

Together, these components implement a practical **Human-in-the-Loop support system**:

1. User chats with bot.
2. Bot responds via Rasa NLU/stories/rules.
3. If confidence is low (or user requests a human), conversation escalates.
4. Agent continues the conversation from dashboard.
5. Agent marks case resolved with problem type + resolution steps.
6. Resolution and feedback are stored for future retraining and quality analysis.

---

## Core features

- **Automated chat responses** via Rasa NLU + dialogue policies.
- **Confidence-based escalation** using custom actions.
- **Live agent handoff** with persisted conversation state.
- **Agent dashboard** with pending queue, response panel, canned replies, and resolution workflow.
- **User feedback capture** (message ratings/comments).
- **Resolution case capture** for continuous improvement/retraining.
- **Local SQLite persistence** for escalations, agent responses, resolution cases, and feedback.
- **Optional website knowledge/training utilities** included in backend scripts.

---

## Architecture overview

### Services

- **Rasa Server** (`:5005`) – intent/entity parsing + dialogue execution.
- **Rasa Action Server** (`:5055`) – custom actions (confidence checks, escalations, data persistence hooks).
- **Flask API Server** (`:5001`) – escalation, agent messaging, feedback, and analytics endpoints for frontend.
- **React Frontend** (`:3000`) – chatbot UI + agent dashboard UI.

### Data flow (high level)

1. Frontend sends user messages to Rasa REST webhook.
2. Custom actions determine confidence / escalation conditions.
3. Escalation is written to SQLite (and escalation JSON artifacts).
4. Agent dashboard polls Flask API for pending escalations.
5. Agent sends responses through Flask API; chatbot polls for agent replies.
6. Resolved cases and user feedback are stored for retraining and reporting.

---

## Repository structure

```text
.
├── rasa-backend/
│   ├── actions/                 # Rasa custom actions
│   ├── data/                    # NLU, stories, rules
│   ├── tests/                   # Rasa conversation tests
│   ├── api_server.py            # Flask API for dashboard/chat sync
│   ├── database.py              # SQLite schema + data access helpers
│   ├── domain.yml               # Assistant domain (intents, responses, slots, actions)
│   ├── config.yml               # Rasa pipeline/policies config
│   ├── endpoints.yml            # Action server/tracker endpoints
│   ├── requirements.txt         # Python deps
│   └── *.py utilities           # retraining, data prep, knowledge scripts
├── react-frontend/
│   ├── src/components/
│   │   ├── Chatbot.js           # End-user chat widget
│   │   └── AgentDashboard.js    # Human agent console
│   └── package.json
└── start_all.bat                # Windows orchestration script (all services)
```

---

## Installation

## 1) Prerequisites

- **Python 3.9–3.10 recommended** (Rasa compatibility dependent)
- **Node.js 18+** and npm
- **Git**
- **Windows** if you plan to use `start_all.bat` as-is (manual startup works on macOS/Linux)

## 2) Clone repository

```bash
git clone <your-repo-url>
cd Human-AI-Feedback-Loop
```

## 3) Backend setup

```bash
cd rasa-backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Initialize database:

```bash
python database.py
```

Train Rasa model:

```bash
rasa train
```

## 4) Frontend setup

```bash
cd ../react-frontend
npm install
```

---

## Running the project

## Option A: Windows one-click start

From repo root:

```bat
start_all.bat
```

This script starts Action Server, Rasa Server, Flask API, and React frontend.

## Option B: Manual start (cross-platform)

Use separate terminals.

### Terminal 1 – Action server

```bash
cd rasa-backend
# activate venv first
rasa run actions
```

### Terminal 2 – Rasa server

```bash
cd rasa-backend
# activate venv first
rasa run --enable-api --cors "*"
```

### Terminal 3 – Flask API

```bash
cd rasa-backend
# activate venv first
python api_server.py
```

### Terminal 4 – React frontend

```bash
cd react-frontend
npm start
```

Open:

- Chatbot / app: `http://localhost:3000`
- Rasa API: `http://localhost:5005`
- Agent/feedback API: `http://localhost:5001`

---

## Configuration

### Backend environment variables

- `WEBSITE_URL` (optional): used by knowledge/training utilities and startup script defaults.

### Frontend environment variables (optional)

Create `react-frontend/.env`:

```env
REACT_APP_RASA_URL=http://localhost:5005/webhooks/rest/webhook
REACT_APP_API_URL=http://localhost:5001/api
```

Defaults already point to localhost if values are not set.

---

## API overview (Flask)

Key endpoints include:

- `GET /api/health`
- `GET /api/escalations/pending`
- `GET /api/escalations/<conversation_id>`
- `POST /api/escalations/<conversation_id>/respond`
- `POST /api/escalations/<conversation_id>/resolve`
- `POST /api/escalations/<conversation_id>/user-message`
- `GET /api/user/<user_id>/messages`
- Feedback/stat endpoints used by dashboard and chatbot

These endpoints back the live human handoff + feedback loop between user chat and agent console.

---

## Primary use cases

- **Customer support copilot**: bot handles common intents, agents handle edge cases.
- **Human fallback for low-confidence AI**: prevent dead-end bot conversations.
- **Continuous quality improvement**: convert resolved human interventions into training examples.
- **Support operations visibility**: monitor pending escalations and response quality.
- **Hybrid chat experience**: seamless transition between AI and live human agent.

---

## Typical workflow for teams

1. Define intents, stories, and responses in Rasa files.
2. Train and run assistant.
3. Let users chat through frontend widget.
4. Review escalations in dashboard.
5. Resolve and categorize cases with clear steps.
6. Use stored resolution cases and feedback to refine training data.
7. Retrain periodically with updated data.

---

## Notes and limitations

- Project currently uses **SQLite**, ideal for local/dev and small-team usage.
- Polling is used for near-real-time updates (not websockets).
- Some knowledge-base/RAG related modules are present but may require careful dependency handling with Rasa versions.
- Existing `chatbot.db` and `escalations/*.json` indicate persistent local state; sanitize before sharing externally.

---

## Suggested next improvements

- Docker Compose for one-command cross-platform startup.
- Production DB (PostgreSQL/MySQL) + migrations.
- WebSocket/SSE messaging for real-time communication.
- Authentication/authorization for agent dashboard.
- CI pipeline for automated training/tests/linting.
- Structured observability (logs/metrics/traces).

---

## License

No explicit license file is currently included in this repository. Add a `LICENSE` file before production/commercial distribution.
