import { useState, useEffect } from 'react';
import { ActiveCall } from '../types';
import { api } from '../services/api';

export function useActiveCalls() {
  const [calls, setCalls] = useState<ActiveCall[]>([]);

  useEffect(() => {
    // Poll for active sessions (fallback when Sync not configured)
    const poll = async () => {
      try {
        const sessions = await api.getSessions();
        setCalls(sessions.map(s => ({
          callSid: s.callSid,
          callerNumber: s.callerNumber,
          startTime: s.startTime,
          csat: s.csat,
          topic: s.topic,
          status: s.status,
        })));
      } catch {}
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  return calls;
}
