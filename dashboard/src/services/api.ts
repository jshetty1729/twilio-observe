const API_BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
}

async function post<T = void>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
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
    return request<any[]>(`${API_BASE}/observe/sessions`);
  },

  async sendCoaching(callSid: string, instruction: string): Promise<any> {
    return post(`${API_BASE}/observe/coach`, { callSid, note: instruction });
  },

  async initiateBarge(callSid: string): Promise<{ status: string; conv_id: string; conf_name: string; token: string }> {
    return post(`${API_BASE}/observe/barge`, { callSid });
  },

  async handBack(callSid: string): Promise<any> {
    return post(`${API_BASE}/observe/handback`, { callSid });
  },
};
