import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Heading, Text, Stack } from '@twilio-paste/core';
import { useActiveCalls } from '../hooks/useActiveCalls';
import { CallCard } from '../components/CallCard';

export const DashboardPage: React.FC = () => {
  const calls = useActiveCalls();
  const navigate = useNavigate();

  return (
    <Box padding="space60" backgroundColor="colorBackgroundBody" minHeight="100vh">
      <Box marginBottom="space60">
        <Heading as="h1" variant="heading10">
          Twilio Observe — AI Agent Supervision
        </Heading>
        <Text as="p" color="colorTextWeak">Real-time monitoring, coaching, and intervention for AI agent calls</Text>
      </Box>

      <Box marginBottom="space40">
        <Heading as="h2" variant="heading20">
          Active AI Agent Calls ({calls.length})
        </Heading>
      </Box>

      {calls.length === 0 ? (
        <Box padding="space60" textAlign="center">
          <Text as="p" color="colorTextWeak">No active calls. Waiting for inbound calls...</Text>
        </Box>
      ) : (
        <Stack orientation="vertical" spacing="space30">
          {calls.map((call) => (
            <CallCard key={call.callSid} call={call} onClick={(sid) => navigate(`/call/${sid}`)} />
          ))}
        </Stack>
      )}
    </Box>
  );
};
