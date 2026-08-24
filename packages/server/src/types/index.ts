export interface TranscriptTurn {
  id: string;
  timestamp: number;
  role: 'customer' | 'ai' | 'supervisor';
  content: string;
}

export interface CallSession {
  callSid: string;
  syncDocumentSid: string;
  status: 'active' | 'coached' | 'barged' | 'completed';
  csat: number;
  topic: string;
  callerNumber: string;
  startTime: number;
  transcript: TranscriptTurn[];
  coachingInstructions: string[];
  systemContext: string;
}

export interface CoachingInstruction {
  callSid: string;
  instruction: string;
  supervisorId: string;
  timestamp: number;
}
