import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { config } from './config.js';
import { callRoutes } from './routes/call.routes.js';
import { tokenRoutes } from './routes/token.routes.js';
import { coachRoutes } from './routes/coach.routes.js';
import { bargeRoutes } from './routes/barge.routes.js';
import { handleRelayConnection } from './routes/relay.routes.js';
import { tacService } from './services/tac.service.js';
import { logger } from './utils/logger.js';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use('/api/calls', callRoutes);
app.use('/api/token', tokenRoutes);
app.use('/api/coach', coachRoutes);
app.use('/api/barge', bargeRoutes);

app.get('/api/sessions', (_req, res) => {
  res.json(tacService.getAllSessions());
});

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() });
});

// HTTP + WebSocket server
const httpServer = createServer(app);

const wss = new WebSocketServer({ server: httpServer });
wss.on('connection', (ws, req) => {
  const url = new URL(req.url || '', `http://${req.headers.host}`);
  const match = url.pathname.match(/^\/ws\/relay\/(.+)$/);
  if (match) {
    const callSid = match[1];
    handleRelayConnection(ws, callSid);
  } else {
    logger.warn(`Unknown WebSocket path: ${url.pathname}`);
    ws.close();
  }
});

httpServer.listen(config.server.port, () => {
  logger.info(`Twilio Observe server running on port ${config.server.port}`);
});

export { app, httpServer as server };
