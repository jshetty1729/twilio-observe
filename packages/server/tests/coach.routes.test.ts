import { describe, it, expect } from 'vitest';
import request from 'supertest';
import express from 'express';
import { coachRoutes } from '../src/routes/coach.routes.js';
import { bargeRoutes } from '../src/routes/barge.routes.js';
import { tacService } from '../src/services/tac.service.js';

const app = express();
app.use(express.json());
app.use('/api/coach', coachRoutes);
app.use('/api/barge', bargeRoutes);

describe('POST /api/coach', () => {
  it('injects coaching instruction into session', async () => {
    tacService.createSession('CA-coach-1', '+15551234567');

    const res = await request(app)
      .post('/api/coach')
      .send({ callSid: 'CA-coach-1', instruction: 'Use the trade-in tool' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('coaching_applied');

    const session = tacService.getSession('CA-coach-1');
    expect(session?.coachingInstructions).toContain('Use the trade-in tool');
    expect(session?.status).toBe('coached');
  });

  it('returns 404 for unknown call', async () => {
    const res = await request(app)
      .post('/api/coach')
      .send({ callSid: 'CA-unknown', instruction: 'test' });

    expect(res.status).toBe(404);
  });

  it('returns 400 when missing fields', async () => {
    const res = await request(app)
      .post('/api/coach')
      .send({ callSid: 'CA-coach-1' });

    expect(res.status).toBe(400);
  });
});

describe('POST /api/barge/initiate', () => {
  it('sets AI to silent co-pilot mode', async () => {
    tacService.createSession('CA-barge-1', '+15551234567');

    const res = await request(app)
      .post('/api/barge/initiate')
      .send({ callSid: 'CA-barge-1' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('barge_initiated');

    const session = tacService.getSession('CA-barge-1');
    expect(session?.status).toBe('barged');
  });
});

describe('POST /api/barge/hand-back', () => {
  it('reactivates AI agent', async () => {
    tacService.createSession('CA-hb-1', '+15551234567');
    tacService.setSilentCopilot('CA-hb-1');

    const res = await request(app)
      .post('/api/barge/hand-back')
      .send({ callSid: 'CA-hb-1' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('hand_back_complete');

    const session = tacService.getSession('CA-hb-1');
    expect(session?.status).toBe('active');
  });
});
