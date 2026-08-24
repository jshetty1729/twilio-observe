import { Router, Request, Response } from 'express';
import { tacService } from '../services/tac.service.js';
import { logger } from '../utils/logger.js';

export const bargeRoutes = Router();

// Supervisor initiates barge — AI becomes silent co-pilot
bargeRoutes.post('/initiate', (req: Request, res: Response) => {
  const { callSid } = req.body;

  if (!callSid) {
    return res.status(400).json({ error: 'callSid required' });
  }

  const session = tacService.getSession(callSid);
  if (!session) {
    return res.status(404).json({ error: 'No active session for this call' });
  }

  // Set AI to silent co-pilot mode
  tacService.setSilentCopilot(callSid);

  // Log barge event in transcript
  tacService.addTranscriptTurn(callSid, {
    id: `barge-${Date.now()}`,
    timestamp: Date.now(),
    role: 'supervisor',
    content: '[BARGE] Supervisor has taken over the conversation.',
  });

  logger.info(`Barge initiated for ${callSid}`);
  res.json({ status: 'barge_initiated', callSid });
});

// Supervisor hands back to AI
bargeRoutes.post('/hand-back', (req: Request, res: Response) => {
  const { callSid } = req.body;

  if (!callSid) {
    return res.status(400).json({ error: 'callSid required' });
  }

  const session = tacService.getSession(callSid);
  if (!session) {
    return res.status(404).json({ error: 'No active session for this call' });
  }

  // Reactivate AI agent
  tacService.reactivateAgent(callSid);

  // Log hand-back event
  tacService.addTranscriptTurn(callSid, {
    id: `handback-${Date.now()}`,
    timestamp: Date.now(),
    role: 'supervisor',
    content: '[HAND BACK] AI agent reactivated.',
  });

  logger.info(`Hand-back for ${callSid}`);
  res.json({ status: 'hand_back_complete', callSid });
});
