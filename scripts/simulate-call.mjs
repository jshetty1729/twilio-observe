#!/usr/bin/env node

/**
 * Simulates the Camping World demo call for testing the supervisor dashboard
 * without needing real Twilio credentials or a phone call.
 *
 * Usage: node scripts/simulate-call.mjs
 *
 * This connects via WebSocket to the local server and simulates the
 * ConversationRelay protocol — sending setup and prompt messages as if
 * a real caller were speaking.
 */

import WebSocket from 'ws';

const SERVER_URL = process.env.SERVER_URL || 'ws://localhost:3001';
const CALL_SID = `CA${Date.now().toString(36)}sim`;

console.log(`\n🎬 Simulating Camping World demo call`);
console.log(`   Call SID: ${CALL_SID}`);
console.log(`   Server: ${SERVER_URL}`);
console.log(`   Dashboard: http://localhost:5173\n`);

const ws = new WebSocket(`${SERVER_URL}/ws/relay/${CALL_SID}`);

const DEMO_SCRIPT = [
  {
    delay: 1000,
    message: {
      type: 'setup',
      sessionId: `VX${CALL_SID}`,
      callSid: CALL_SID,
      from: '+15551234567',
      to: '+15559876543',
      direction: 'inbound',
      callStatus: 'RINGING',
      customParameters: {},
    },
    description: 'Call connected',
  },
  {
    delay: 3000,
    message: {
      type: 'prompt',
      voicePrompt: "I've got a 2017 Keystone Cougar. What kind of trade-in value am I looking at toward a Montana High Country?",
      lang: 'en-US',
      last: true,
    },
    description: 'Customer asks about trade-in value',
  },
  {
    delay: 8000,
    message: {
      type: 'prompt',
      voicePrompt: "About 34,000 miles, very good condition. We've kept it well maintained.",
      lang: 'en-US',
      last: true,
    },
    description: 'Customer provides vehicle details',
  },
  {
    delay: 12000,
    message: {
      type: 'prompt',
      voicePrompt: "Yeah, that sounds good. I'm thinking Saturday.",
      lang: 'en-US',
      last: true,
    },
    description: 'Customer wants to schedule (positive)',
  },
  {
    delay: 18000,
    message: {
      type: 'prompt',
      voicePrompt: "3 to 5 business days? I just said I want to come Saturday. That's ridiculous.",
      lang: 'en-US',
      last: true,
    },
    description: 'Customer frustrated (CSAT should drop)',
  },
  {
    delay: 23000,
    message: {
      type: 'prompt',
      voicePrompt: "That's ridiculous. I've been on this call for ten minutes and you can't just book a Saturday slot?",
      lang: 'en-US',
      last: true,
    },
    description: 'Customer very frustrated — barge opportunity',
  },
];

ws.on('open', () => {
  console.log('✅ WebSocket connected to server\n');

  DEMO_SCRIPT.forEach(({ delay, message, description }) => {
    setTimeout(() => {
      console.log(`⏱  [${Math.round(delay / 1000)}s] ${description}`);
      if (message.type === 'prompt') {
        console.log(`   Customer: "${message.voicePrompt}"`);
      }
      ws.send(JSON.stringify(message));
    }, delay);
  });

  // End after script completes
  setTimeout(() => {
    console.log('\n🎬 Demo script complete.');
    console.log('   The call remains active for you to test Coach and Barge.');
    console.log('   Open http://localhost:5173 and click on the active call.');
    console.log('   Press Ctrl+C to end.\n');
  }, 25000);
});

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === 'text') {
    console.log(`   AI: "${msg.token?.slice(0, 80)}${msg.token?.length > 80 ? '...' : ''}"\n`);
  }
});

ws.on('error', (err) => {
  console.error('❌ WebSocket error:', err.message);
  console.log('   Make sure the server is running: pnpm dev:server');
  process.exit(1);
});

ws.on('close', () => {
  console.log('WebSocket closed');
});

// Keep alive
process.on('SIGINT', () => {
  ws.close();
  process.exit(0);
});
