import { Router, Request, Response } from 'express';
import twilio from 'twilio';
import { config } from '../config.js';
import { logger } from '../utils/logger.js';

export const tokenRoutes = Router();

tokenRoutes.get('/sync', (_req: Request, res: Response) => {
  if (!config.twilio.apiKey || !config.twilio.apiSecret) {
    logger.warn('Twilio API credentials not configured — returning mock token');
    return res.json({ token: 'mock-sync-token' });
  }

  const AccessToken = twilio.jwt.AccessToken;
  const SyncGrant = AccessToken.SyncGrant;

  const token = new AccessToken(
    config.twilio.accountSid,
    config.twilio.apiKey,
    config.twilio.apiSecret,
    { identity: 'supervisor-1' }
  );

  const syncGrant = new SyncGrant({
    serviceSid: config.twilio.syncServiceSid,
  });
  token.addGrant(syncGrant);

  res.json({ token: token.toJwt() });
});

tokenRoutes.get('/voice', (_req: Request, res: Response) => {
  if (!config.twilio.apiKey || !config.twilio.apiSecret) {
    logger.warn('Twilio API credentials not configured — returning mock token');
    return res.json({ token: 'mock-voice-token' });
  }

  const AccessToken = twilio.jwt.AccessToken;
  const VoiceGrant = AccessToken.VoiceGrant;

  const token = new AccessToken(
    config.twilio.accountSid,
    config.twilio.apiKey,
    config.twilio.apiSecret,
    { identity: 'supervisor-1' }
  );

  const voiceGrant = new VoiceGrant({
    outgoingApplicationSid: config.twilio.twimlAppSid,
    incomingAllow: true,
  });
  token.addGrant(voiceGrant);

  res.json({ token: token.toJwt() });
});
