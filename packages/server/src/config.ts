import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

dotenv.config({ path: resolve(__dirname, '../../../.env') });

export const config = {
  twilio: {
    accountSid: process.env.TWILIO_ACCOUNT_SID || '',
    authToken: process.env.TWILIO_AUTH_TOKEN || '',
    apiKey: process.env.TWILIO_API_KEY || '',
    apiSecret: process.env.TWILIO_API_SECRET || '',
    syncServiceSid: process.env.TWILIO_SYNC_SERVICE_SID || '',
    phoneNumber: process.env.TWILIO_TRUNKING_NUMBER || '',
    twimlAppSid: process.env.TWILIO_TWIML_APP_SID || '',
    ciServiceSid: process.env.TWILIO_CI_SERVICE_SID || '',
  },
  gemini: {
    apiKey: process.env.GEMINI_API_KEY || '',
  },
  server: {
    port: parseInt(process.env.PORT || '3001'),
    ngrokUrl: process.env.NGROK_URL || 'http://localhost:3001',
  },
};
