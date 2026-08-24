import { Router, Request, Response } from 'express';
import { tacService } from '../services/tac.service.js';
import { logger } from '../utils/logger.js';

export const coachRoutes = Router();

coachRoutes.post('/', (req: Request, res: Response) => {
  const { callSid, instruction } = req.body;

  if (!callSid || !instruction) {
    return res.status(400).json({ error: 'callSid and instruction required' });
  }

  const session = tacService.getSession(callSid);
  if (!session) {
    return res.status(404).json({ error: 'No active session for this call' });
  }

  try {
    tacService.injectCoaching(callSid, instruction);

    // Add coaching note to transcript for visibility
    tacService.addTranscriptTurn(callSid, {
      id: `coach-${Date.now()}`,
      timestamp: Date.now(),
      role: 'supervisor',
      content: `[COACHING] ${instruction}`,
    });

    logger.info(`Coach sent for ${callSid}`);
    res.json({ status: 'coaching_applied', callSid });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});
