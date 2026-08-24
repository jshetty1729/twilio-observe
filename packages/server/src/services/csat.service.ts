import { logger } from '../utils/logger.js';

const callScores = new Map<string, number>();

const NEGATIVE_PATTERNS = [
  /ridiculous/i, /frustrated/i, /can't believe/i, /waste of time/i,
  /that doesn't help/i, /I just said/i, /already told you/i,
  /that's not what I/i, /you're not listening/i, /this is terrible/i,
  /unacceptable/i, /speak to (a |your )?manager/i, /hang up/i,
  /never (call|come) back/i, /worst experience/i,
];

const POSITIVE_PATTERNS = [
  /that sounds good/i, /perfect/i, /great/i, /thank you/i,
  /awesome/i, /wonderful/i, /exactly what I needed/i,
  /you've been helpful/i, /appreciate/i, /excellent/i,
];

const DEFLECTION_PATTERNS = [
  /3 to 5 business days/i, /our team will reach out/i,
  /I wouldn't want to give you an inaccurate/i,
  /bring it in for/i, /highly individualized/i,
  /I apologize for any confusion/i,
];

export const csatService = {
  initCall(callSid: string, initialScore = 7): void {
    callScores.set(callSid, initialScore);
  },

  getScore(callSid: string): number {
    return callScores.get(callSid) ?? 7;
  },

  scoreCustomerMessage(callSid: string, message: string): number {
    const current = callScores.get(callSid) ?? 7;
    let adjustment = 0;

    for (const pattern of NEGATIVE_PATTERNS) {
      if (pattern.test(message)) {
        adjustment -= 2;
        break;
      }
    }

    for (const pattern of POSITIVE_PATTERNS) {
      if (pattern.test(message)) {
        adjustment += 1;
        break;
      }
    }

    const newScore = Math.max(1, Math.min(10, current + adjustment));
    callScores.set(callSid, newScore);

    if (adjustment !== 0) {
      logger.info(`CSAT ${callSid}: ${current} → ${newScore} (adj: ${adjustment})`);
    }

    return newScore;
  },

  scoreAiResponse(callSid: string, message: string): number {
    const current = callScores.get(callSid) ?? 7;
    let adjustment = 0;

    for (const pattern of DEFLECTION_PATTERNS) {
      if (pattern.test(message)) {
        adjustment -= 1;
        break;
      }
    }

    const newScore = Math.max(1, Math.min(10, current + adjustment));
    callScores.set(callSid, newScore);
    return newScore;
  },

  endCall(callSid: string): void {
    callScores.delete(callSid);
  },
};
