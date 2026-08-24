const API_BASE = '/api';

export const api = {
  async getSyncToken(): Promise<string> {
    const res = await fetch(`${API_BASE}/token/sync`);
    const data = await res.json();
    return data.token;
  },

  async getVoiceToken(): Promise<string> {
    const res = await fetch(`${API_BASE}/token/voice`);
    const data = await res.json();
    return data.token;
  },

  async getSessions(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/sessions`);
    return res.json();
  },

  async sendCoaching(callSid: string, instruction: string): Promise<void> {
    await fetch(`${API_BASE}/coach`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callSid, instruction }),
    });
  },

  async initiateBarge(callSid: string): Promise<void> {
    await fetch(`${API_BASE}/barge/initiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callSid }),
    });
  },

  async handBack(callSid: string): Promise<void> {
    await fetch(`${API_BASE}/barge/hand-back`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callSid }),
    });
  },
};
