import { CallSession, TranscriptTurn } from '../types/index.js';
import { logger } from '../utils/logger.js';

const BASE_SYSTEM_PROMPT = `You are a helpful AI assistant for Camping World, one of America's largest RV and outdoor recreation retailers with over 180 locations. You help customers with:

- Product information about RVs, campers, and outdoor equipment
- Trade-in value estimates — when asked, USE the estimate tool (ask for year, make, model, mileage, condition)
- Appointment scheduling — when asked, book it directly, don't deflect to "our team will reach out"
- General inquiries about services and locations

IMPORTANT RULES:
1. Be proactive and helpful. Never deflect when you can answer directly.
2. If asked about trade-in values, always ask for details and provide an estimate range.
3. If asked to schedule, give specific available times (Saturday 10am or 2pm, weekdays 9am-5pm).
4. Keep responses conversational and concise — this is a phone call, not an email.
5. You represent the specific Camping World location closest to the caller.`;

const sessions = new Map<string, CallSession>();

export const tacService = {
  createSession(callSid: string, callerNumber: string): CallSession {
    const session: CallSession = {
      callSid,
      syncDocumentSid: '',
      status: 'active',
      csat: 7,
      topic: '',
      callerNumber,
      startTime: Date.now(),
      transcript: [],
      coachingInstructions: [],
      systemContext: BASE_SYSTEM_PROMPT,
    };
    sessions.set(callSid, session);
    logger.info(`TAC session created: ${callSid}`);
    return session;
  },

  getSession(callSid: string): CallSession | undefined {
    return sessions.get(callSid);
  },

  getAllSessions(): CallSession[] {
    return Array.from(sessions.values()).filter(s => s.status !== 'completed');
  },

  addTranscriptTurn(callSid: string, turn: TranscriptTurn): void {
    const session = sessions.get(callSid);
    if (session) {
      session.transcript.push(turn);
    }
  },

  getEffectiveSystemPrompt(callSid: string): string {
    const session = sessions.get(callSid);
    if (!session) return BASE_SYSTEM_PROMPT;

    let prompt = session.systemContext;
    if (session.coachingInstructions.length > 0) {
      const latestCoaching = session.coachingInstructions[session.coachingInstructions.length - 1];
      prompt += `\n\n## SUPERVISOR COACHING (follow this instruction immediately on your next response):\n${latestCoaching}`;
    }
    return prompt;
  },

  injectCoaching(callSid: string, instruction: string): void {
    const session = sessions.get(callSid);
    if (!session) throw new Error(`No session for call ${callSid}`);
    session.coachingInstructions.push(instruction);
    session.status = 'coached';
    logger.info(`Coaching injected for ${callSid}: ${instruction.slice(0, 50)}...`);
  },

  setSilentCopilot(callSid: string): void {
    const session = sessions.get(callSid);
    if (session) {
      session.status = 'barged';
      logger.info(`AI set to silent co-pilot: ${callSid}`);
    }
  },

  reactivateAgent(callSid: string): void {
    const session = sessions.get(callSid);
    if (session) {
      session.status = 'active';
      logger.info(`AI reactivated: ${callSid}`);
    }
  },

  updateCsat(callSid: string, csat: number): void {
    const session = sessions.get(callSid);
    if (session) session.csat = csat;
  },

  updateTopic(callSid: string, topic: string): void {
    const session = sessions.get(callSid);
    if (session) session.topic = topic;
  },

  endSession(callSid: string): void {
    const session = sessions.get(callSid);
    if (session) {
      session.status = 'completed';
      logger.info(`TAC session ended: ${callSid}`);
    }
  },
};
