# Twilio Observe — Real-Time AI Agent Supervision

Real-time Monitor, Coach, and Barge capabilities for AI agent calls. Built for Tweek 2026.

## Quick Start

```bash
# Install dependencies
pnpm install

# Copy environment variables
cp .env.example .env
# Edit .env with your Twilio credentials and Gemini API key

# Start both server and dashboard
pnpm dev
```

This starts:
- **Server** at `http://localhost:3001` — Express + WebSocket for ConversationRelay
- **Dashboard** at `http://localhost:5173` — Supervisor UI (proxies API calls to server)

## Running Without Twilio Credentials

The app works in **demo mode** without Twilio credentials:
- Sync service gracefully skips (logs warnings)
- Token endpoints return mock tokens
- Use the demo simulation script to test the UI

### Demo Simulation

To simulate a call without a real phone:

```bash
# In a separate terminal, with the server running:
node scripts/simulate-call.mjs
```

This creates a fake session and simulates the Camping World demo conversation.

## Architecture

```
Customer Phone → Twilio Voice → ConversationRelay → WebSocket → Our Server → Gemini
                                                                      ↓
                                                              Twilio Sync (real-time)
                                                                      ↓
                                                        Supervisor Dashboard (React)
```

## Key Features

- **Monitor** — See all active AI agent calls, live transcript, CSAT score
- **Coach** — Inject instructions into the AI's context mid-call (invisible to customer)
- **Barge** — Take over the call when AI is failing; AI becomes silent co-pilot

## Project Structure

```
twilio-observe/
├── packages/
│   ├── server/          # Node.js backend
│   │   ├── src/
│   │   │   ├── index.ts           # Express + WebSocket server
│   │   │   ├── routes/
│   │   │   │   ├── call.routes.ts   # Inbound call TwiML
│   │   │   │   ├── relay.routes.ts  # ConversationRelay WebSocket
│   │   │   │   ├── coach.routes.ts  # Coach endpoint
│   │   │   │   ├── barge.routes.ts  # Barge/hand-back endpoints
│   │   │   │   └── token.routes.ts  # Sync/Voice token gen
│   │   │   └── services/
│   │   │       ├── tac.service.ts   # AI agent session management
│   │   │       ├── gemini.service.ts # Gemini LLM integration
│   │   │       ├── csat.service.ts  # Real-time CSAT scoring
│   │   │       └── sync.service.ts  # Twilio Sync relay
│   │   └── tests/
│   └── dashboard/       # React supervisor UI
│       └── src/
│           ├── pages/         # DashboardPage, CallDetailPage
│           ├── components/    # TranscriptView, CoachPanel, BargeControls
│           └── hooks/         # useActiveCalls, useCallDetail
└── scripts/
    └── simulate-call.mjs  # Demo simulation script
```

## Tech Stack

- **Backend**: Node.js, Express, WebSocket (ws), TypeScript
- **Frontend**: React 18, Vite, Twilio Paste UI
- **Twilio**: ConversationRelay, Sync, Voice JS SDK, Conversation Intelligence
- **AI**: Google Gemini 2.0 Flash

## Tests

```bash
pnpm --filter @twilio-observe/server test
```
