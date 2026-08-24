const API_BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
}

async function post(url: string, body: unknown): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${error}`);
  }
}

export const api = {
  async getSyncToken(): Promise<string> {
    const data = await request<{ token: string }>(`${API_BASE}/token/sync`);
    return data.token;
  },

  async getVoiceToken(): Promise<string> {
    const data = await request<{ token: string }>(`${API_BASE}/token/voice`);
    return data.token;
  },

  async getSessions(): Promise<any[]> {
    return request<any[]>(`${API_BASE}/sessions`);
  },

  async sendCoaching(callSid: string, instruction: string): Promise<void> {
    await post(`${API_BASE}/coach`, { callSid, instruction });
  },

  async initiateBarge(callSid: string): Promise<void> {
    await post(`${API_BASE}/barge/initiate`, { callSid });
  },

  async handBack(callSid: string): Promise<void> {
    await post(`${API_BASE}/barge/hand-back`, { callSid });
  },
};
