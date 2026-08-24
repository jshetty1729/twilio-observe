import { WebSocket } from 'ws';
import { tacService } from '../services/tac.service.js';
import { geminiService } from '../services/gemini.service.js';
import { csatService } from '../services/csat.service.js';
import { logger } from '../utils/logger.js';
import { TranscriptTurn } from '../types/index.js';

interface SetupMessage {
  type: 'setup';
  sessionId: string;
  callSid: string;
  from: string;
  to: string;
  customParameters?: Record<string, string>;
}

interface PromptMessage {
  type: 'prompt';
  voicePrompt: string;
  lang: string;
  last: boolean;
}

interface InterruptMessage {
  type: 'interrupt';
  utteranceUntilInterrupt: string;
  durationUntilInterruptMs: number;
}

type RelayMessage = SetupMessage | PromptMessage | InterruptMessage | { type: string };

export function handleRelayConnection(ws: WebSocket, callSid: string) {
  logger.info(`ConversationRelay WebSocket connected: ${callSid}`);

  let sessionCallSid = callSid;

  ws.on('message', async (data: Buffer) => {
    try {
      const message: RelayMessage = JSON.parse(data.toString());

      switch (message.type) {
        case 'setup': {
          const setup = message as SetupMessage;
          sessionCallSid = setup.callSid || callSid;
          if (!tacService.getSession(sessionCallSid)) {
            tacService.createSession(sessionCallSid, setup.from);
          }
          csatService.initCall(sessionCallSid);
          logger.info(`CR session setup: ${sessionCallSid} from ${setup.from}`);
          break;
        }

        case 'prompt': {
          const prompt = message as PromptMessage;
          if (!prompt.last) break;

          const session = tacService.getSession(sessionCallSid);
          if (!session) {
            logger.error(`No session for prompt: ${sessionCallSid}`);
            break;
          }

          if (session.status === 'barged') {
            logger.info(`Ignoring prompt — AI is in silent co-pilot: ${sessionCallSid}`);
            break;
          }

          const customerTurn: TranscriptTurn = {
            id: `cust-${Date.now()}`,
            timestamp: Date.now(),
            role: 'customer',
            content: prompt.voicePrompt,
          };
          tacService.addTranscriptTurn(sessionCallSid, customerTurn);

          const systemPrompt = tacService.getEffectiveSystemPrompt(sessionCallSid);
          const aiResponse = await geminiService.generateResponse(
            systemPrompt,
            session.transcript,
            prompt.voicePrompt
          );

          const aiTurn: TranscriptTurn = {
            id: `ai-${Date.now()}`,
            timestamp: Date.now(),
            role: 'ai',
            content: aiResponse,
          };
          tacService.addTranscriptTurn(sessionCallSid, aiTurn);

          // Score CSAT
          csatService.scoreCustomerMessage(sessionCallSid, prompt.voicePrompt);
          csatService.scoreAiResponse(sessionCallSid, aiResponse);
          const newCsat = csatService.getScore(sessionCallSid);
          tacService.updateCsat(sessionCallSid, newCsat);

          ws.send(JSON.stringify({
            type: 'text',
            token: aiResponse,
            last: true,
          }));

          break;
        }

        case 'interrupt': {
          const interrupt = message as InterruptMessage;
          logger.info(`Caller interrupted at: "${interrupt.utteranceUntilInterrupt}"`);
          break;
        }

        default:
          logger.info(`Unhandled CR message type: ${message.type}`);
      }
    } catch (error) {
      logger.error('Error processing relay message', error);
    }
  });

  ws.on('close', () => {
    logger.info(`ConversationRelay WebSocket closed: ${sessionCallSid}`);
  });

  ws.on('error', (error) => {
    logger.error(`WebSocket error: ${sessionCallSid}`, error);
  });
}
