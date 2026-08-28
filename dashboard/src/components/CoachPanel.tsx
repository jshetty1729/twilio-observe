import React, { useState } from 'react';
import { Box, Heading, TextArea, Button, Label, HelpText } from '@twilio-paste/core';
import { api } from '../services/api';

interface CoachPanelProps {
  callSid: string;
}

export const CoachPanel: React.FC<CoachPanelProps> = ({ callSid }) => {
  const [instruction, setInstruction] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    if (!instruction.trim()) return;
    setSending(true);
    try {
      await api.sendCoaching(callSid, instruction);
      setSent(true);
      setInstruction('');
      setTimeout(() => setSent(false), 3000);
    } catch (error) {
      console.error('Failed to send coaching:', error);
    } finally {
      setSending(false);
    }
  };

  return (
    <Box>
      <Box marginBottom="space30">
        <Heading as="h3" variant="heading30">
          Coach AI Agent
        </Heading>
      </Box>
      <Label htmlFor="coaching-input">Coaching Instruction</Label>
      <TextArea
        id="coaching-input"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="e.g., Use the trade-in estimation tool — ask for mileage and condition..."
      />
      <HelpText id="coaching-help">
        Injected into the AI agent's context before its next response. Customer won't hear this.
      </HelpText>
      <Box marginTop="space30">
        <Button
          variant="primary"
          onClick={handleSend}
          loading={sending}
          disabled={!instruction.trim()}
        >
          {sent ? 'Queued!' : 'Send Coaching'}
        </Button>
      </Box>
    </Box>
  );
};
