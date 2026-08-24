import React, { useState } from 'react';
import { Box, Heading, TextArea, Button, Label, HelpText } from '@twilio-paste/core';
import { api } from '../services/api';

interface CoachPanelProps {
  callSid: string;
  disabled?: boolean;
}

export const CoachPanel: React.FC<CoachPanelProps> = ({ callSid, disabled }) => {
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
        disabled={disabled}
      />
      <HelpText id="coaching-help">
        Injected into the AI agent's context before its next response. Customer won't see this.
      </HelpText>
      <Box marginTop="space30">
        <Button
          variant="primary"
          onClick={handleSend}
          loading={sending}
          disabled={disabled || !instruction.trim()}
        >
          {sent ? 'Coaching Sent' : 'Send Coaching'}
        </Button>
      </Box>
    </Box>
  );
};
