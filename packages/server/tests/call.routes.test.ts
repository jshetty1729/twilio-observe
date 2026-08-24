import { describe, it, expect } from 'vitest';
import request from 'supertest';
import express from 'express';
import { callRoutes } from '../src/routes/call.routes.js';

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use('/api/calls', callRoutes);

describe('POST /api/calls/inbound', () => {
  it('returns TwiML with ConversationRelay', async () => {
    const res = await request(app)
      .post('/api/calls/inbound')
      .send({ CallSid: 'CA123test', From: '+15551234567' });

    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toContain('text/xml');
    expect(res.text).toContain('<Connect');
    expect(res.text).toContain('ConversationRelay');
    expect(res.text).toContain('ws://');
    expect(res.text).toContain('CA123test');
  });

  it('includes welcome greeting', async () => {
    const res = await request(app)
      .post('/api/calls/inbound')
      .send({ CallSid: 'CA456', From: '+15559876543' });

    expect(res.text).toContain('welcomeGreeting=');
    expect(res.text).toContain('Camping World');
  });
});

describe('POST /api/calls/connect-action', () => {
  it('returns Conference TwiML when handoff reason is barge', async () => {
    const res = await request(app)
      .post('/api/calls/connect-action')
      .send({
        CallSid: 'CA789',
        HandoffData: JSON.stringify({ reason: 'barge' }),
      });

    expect(res.status).toBe(200);
    expect(res.text).toContain('<Conference');
    expect(res.text).toContain('CA789-conference');
  });

  it('returns Hangup TwiML when no barge reason', async () => {
    const res = await request(app)
      .post('/api/calls/connect-action')
      .send({ CallSid: 'CA000', HandoffData: '' });

    expect(res.status).toBe(200);
    expect(res.text).toContain('<Hangup');
  });
});
