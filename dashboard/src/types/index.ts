export interface TranscriptTurn {
  id: string;
  timestamp: number;
  role: 'customer' | 'ai' | 'supervisor' | 'coach' | 'summary';
  content: string;
}

export interface ActiveCall {
  callSid: string;
  callerNumber: string;
  startTime: number;
  csat: number;
  topic: string;
  sentiment: string;
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
