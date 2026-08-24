import { useState, useEffect } from 'react';
import { CallDetail } from '../types';

export function useCallDetail(callSid: string) {
  const [detail, setDetail] = useState<CallDetail | null>(null);

  useEffect(() => {
    if (!callSid) return;

    const poll = async () => {
      try {
        const res = await fetch(`/api/sessions`);
        const sessions = await res.json();
        const session = sessions.find((s: any) => s.callSid === callSid);
        if (session) {
          setDetail({
            callSid: session.callSid,
            callerNumber: session.callerNumber,
            startTime: session.startTime,
            csat: session.csat,
            topic: session.topic,
            status: session.status,
            transcript: session.transcript || [],
            alerts: [],
          });
        }
      } catch {}
    };

    poll();
    const interval = setInterval(poll, 1000);
    return () => clearInterval(interval);
  }, [callSid]);

  return detail;
}
