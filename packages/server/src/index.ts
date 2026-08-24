import express from 'express';
import cors from 'cors';
import { config } from './config.js';
import { callRoutes } from './routes/call.routes.js';
import { logger } from './utils/logger.js';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use('/api/calls', callRoutes);

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() });
});

const server = app.listen(config.server.port, () => {
  logger.info(`Twilio Observe server running on port ${config.server.port}`);
});

export { app, server };
