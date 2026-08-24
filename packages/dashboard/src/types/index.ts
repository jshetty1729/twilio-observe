export interface TranscriptTurn {
  id: string;
  timestamp: number;
  role: 'customer' | 'ai' | 'supervisor';
  content: string;
}

export interface ActiveCall {
  callSid: string;
  callerNumber: string;
  startTime: number;
  csat: number;
  topic: string;
  status: 'active' | 'coached' | 'barged' | 'completed';
}

export interface CallDetail extends ActiveCall {
  transcript: TranscriptTurn[];
  alerts: Alert[];
}

export interface Alert {
  type: string;
  message: string;
  timestamp: number;
}
