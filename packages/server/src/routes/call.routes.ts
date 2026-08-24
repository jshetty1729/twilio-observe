import { Router, Request, Response } from 'express';
import { config } from '../config.js';
import { logger } from '../utils/logger.js';

export const callRoutes = Router();

// Handle inbound call — return TwiML connecting to ConversationRelay
callRoutes.post('/inbound', (req: Request, res: Response) => {
  const { CallSid, From } = req.body;
  logger.info(`Inbound call: ${CallSid} from ${From}`);

  const wsUrl = `${config.server.ngrokUrl.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/relay/${CallSid}`;

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="${config.server.ngrokUrl}/api/calls/connect-action">
    <ConversationRelay
      url="${wsUrl}"
      voice="en-US-Journey-O"
      ttsProvider="Google"
      transcriptionProvider="Deepgram"
      welcomeGreeting="Welcome to Camping World! I'm here to help you with product information, trade-in estimates, and appointment scheduling. What can I help you with today?"
      interruptible="speech"
      intelligenceService="${config.twilio.ciServiceSid}"
    />
  </Connect>
</Response>`;

  res.type('text/xml');
  res.send(twiml);
});

// Connect action callback — fires when ConversationRelay session ends
// Used for barge: returns Conference TwiML when handoffData indicates barge
callRoutes.post('/connect-action', (req: Request, res: Response) => {
  const { CallSid, HandoffData } = req.body;
  logger.info(`Connect action for ${CallSid}`, HandoffData);

  let handoff: { reason?: string } = {};
  try {
    handoff = HandoffData ? JSON.parse(HandoffData) : {};
  } catch {}

  if (handoff.reason === 'barge') {
    // Put caller into a conference for supervisor to join
    const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Conference statusCallback="${config.server.ngrokUrl}/api/calls/conference-status" statusCallbackEvent="join leave end">${CallSid}-conference</Conference>
  </Dial>
</Response>`;
    res.type('text/xml');
    res.send(twiml);
  } else {
    // Normal end — hang up
    const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Hangup/>
</Response>`;
    res.type('text/xml');
    res.send(twiml);
  }
});

// Conference status callback
callRoutes.post('/conference-status', (req: Request, res: Response) => {
  const { ConferenceSid, StatusCallbackEvent, CallSid } = req.body;
  logger.info(`Conference ${ConferenceSid}: ${StatusCallbackEvent} - ${CallSid}`);
  res.sendStatus(200);
});
