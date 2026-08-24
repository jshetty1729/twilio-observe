import twilio from 'twilio';
import { config } from '../config.js';
import { TranscriptTurn } from '../types/index.js';
import { logger } from '../utils/logger.js';

let client: ReturnType<typeof twilio> | null = null;

function getClient() {
  if (!client && config.twilio.accountSid && config.twilio.authToken) {
    client = twilio(config.twilio.accountSid, config.twilio.authToken);
  }
  return client;
}

function getSyncService() {
  const c = getClient();
  if (!c) return null;
  return c.sync.v1.services(config.twilio.syncServiceSid);
}

export const syncService = {
  async createCallDocument(callSid: string, callerNumber: string): Promise<void> {
    const svc = getSyncService();
    if (!svc) {
      logger.warn('Sync service not configured — skipping document creation');
      return;
    }

    try {
      await svc.documents.create({
        uniqueName: `call-${callSid}`,
        data: {
          callSid,
          callerNumber,
          startTime: Date.now(),
          status: 'active',
          transcript: [],
          csat: 7,
          topic: '',
          alerts: [],
        },
      });

      try {
        await svc.maps('active-calls').mapItems.create({
          key: callSid,
          data: { callSid, callerNumber, startTime: Date.now(), csat: 7, topic: '', status: 'active' },
        });
      } catch (mapError: any) {
        if (mapError.code === 20404) {
          await svc.maps.create({ uniqueName: 'active-calls' });
          await svc.maps('active-calls').mapItems.create({
            key: callSid,
            data: { callSid, callerNumber, startTime: Date.now(), csat: 7, topic: '', status: 'active' },
          });
        } else {
          throw mapError;
        }
      }

      logger.info(`Sync document created for ${callSid}`);
    } catch (error) {
      logger.error(`Failed to create Sync document for ${callSid}`, error);
    }
  },

  async addTranscriptTurn(callSid: string, turn: TranscriptTurn): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.transcript.push(turn);
      await svc.documents(`call-${callSid}`).update({ data });
    } catch (error) {
      logger.error(`Failed to add transcript turn for ${callSid}`, error);
    }
  },

  async updateCsat(callSid: string, csat: number): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.csat = csat;
      await svc.documents(`call-${callSid}`).update({ data });

      await svc.maps('active-calls').mapItems(callSid).update({
        data: { callSid, callerNumber: data.callerNumber, startTime: data.startTime, csat, topic: data.topic, status: data.status },
      });
    } catch (error) {
      logger.error(`Failed to update CSAT for ${callSid}`, error);
    }
  },

  async updateTopic(callSid: string, topic: string): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.topic = topic;
      await svc.documents(`call-${callSid}`).update({ data });

      await svc.maps('active-calls').mapItems(callSid).update({
        data: { callSid, callerNumber: data.callerNumber, startTime: data.startTime, csat: data.csat, topic, status: data.status },
      });
    } catch (error) {
      logger.error(`Failed to update topic for ${callSid}`, error);
    }
  },

  async addAlert(callSid: string, alert: { type: string; message: string }): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.alerts.push({ ...alert, timestamp: Date.now() });
      await svc.documents(`call-${callSid}`).update({ data });
    } catch (error) {
      logger.error(`Failed to add alert for ${callSid}`, error);
    }
  },

  async updateStatus(callSid: string, status: string): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.status = status;
      await svc.documents(`call-${callSid}`).update({ data });

      await svc.maps('active-calls').mapItems(callSid).update({
        data: { callSid, callerNumber: data.callerNumber, startTime: data.startTime, csat: data.csat, topic: data.topic, status },
      });
    } catch (error) {
      logger.error(`Failed to update status for ${callSid}`, error);
    }
  },

  async endCall(callSid: string): Promise<void> {
    const svc = getSyncService();
    if (!svc) return;

    try {
      const doc = await svc.documents(`call-${callSid}`).fetch();
      const data = doc.data as any;
      data.status = 'completed';
      await svc.documents(`call-${callSid}`).update({ data });

      await svc.maps('active-calls').mapItems(callSid).remove();
    } catch (error) {
      logger.error(`Failed to end call ${callSid}`, error);
    }
  },
};
