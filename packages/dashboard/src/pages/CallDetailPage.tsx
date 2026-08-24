import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Button, Heading, Text, Separator } from '@twilio-paste/core';
import { useCallDetail } from '../hooks/useCallDetail';
import { TranscriptView } from '../components/TranscriptView';
import { CsatIndicator } from '../components/CsatIndicator';
import { CoachPanel } from '../components/CoachPanel';
import { BargeControls } from '../components/BargeControls';

export const CallDetailPage: React.FC = () => {
  const { callSid } = useParams<{ callSid: string }>();
  const navigate = useNavigate();
  const detail = useCallDetail(callSid!);

  if (!detail) {
    return (
      <Box padding="space60">
        <Text as="p">Loading call details...</Text>
      </Box>
    );
  }

  return (
    <Box padding="space60" backgroundColor="colorBackgroundBody" minHeight="100vh">
      <Button variant="link" onClick={() => navigate('/')}>
        Back to Active Calls
      </Button>

      <Box marginTop="space40" marginBottom="space40">
        <Heading as="h2" variant="heading20">
          Call: {detail.callerNumber || detail.callSid}
        </Heading>
        <Box display="flex" columnGap="space60" marginTop="space20">
          <CsatIndicator score={detail.csat} />
          {detail.topic && <Text as="p" color="colorTextWeak">Topic: {detail.topic}</Text>}
        </Box>
      </Box>

      <Box display="flex" columnGap="space60">
        <Box flex="1">
          <TranscriptView transcript={detail.transcript} />
        </Box>
        <Box width="350px">
          <CoachPanel callSid={callSid!} disabled={detail.status === 'barged'} />
          <Separator orientation="horizontal" verticalSpacing="space50" />
          <BargeControls callSid={callSid!} status={detail.status} />
        </Box>
      </Box>
    </Box>
  );
};
