import React, { useRef, useEffect } from 'react';
import { Box, Text, Heading } from '@twilio-paste/core';
import { TranscriptTurn } from '../types';

interface TranscriptViewProps {
  transcript: TranscriptTurn[];
}

export const TranscriptView: React.FC<TranscriptViewProps> = ({ transcript }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript.length]);

  return (
    <Box>
      <Box marginBottom="space30">
        <Heading as="h3" variant="heading30">
          Live Transcript
        </Heading>
      </Box>
      <Box maxHeight="500px" overflowY="auto" padding="space30" backgroundColor="colorBackgroundBody">
        {transcript.length === 0 && (
          <Text as="p" color="colorTextWeak">Waiting for conversation...</Text>
        )}
        {transcript.map((turn) => (
          <Box
            key={turn.id}
            display="flex"
            justifyContent={
              turn.role === 'ai' ? 'flex-end' :
              (turn.role === 'coach' || turn.role === 'summary' || turn.role === 'supervisor') ? 'center' :
              'flex-start'
            }
            marginBottom="space30"
          >
            <Box
              backgroundColor={
                turn.role === 'customer' ? 'colorBackgroundPrimaryWeakest' :
                turn.role === 'ai' ? 'colorBackgroundSuccessWeakest' :
                turn.role === 'coach' ? 'colorBackgroundDestructiveWeakest' :
                turn.role === 'summary' ? 'colorBackgroundNew' :
                'colorBackgroundWarningWeakest'
              }
              padding="space30"
              borderRadius="borderRadius20"
              maxWidth={(turn.role === 'coach' || turn.role === 'summary' || turn.role === 'supervisor') ? '90%' : '70%'}
              borderLeftWidth={(turn.role === 'coach' || turn.role === 'summary' || turn.role === 'supervisor') ? 'borderWidth30' : undefined}
              borderLeftStyle={(turn.role === 'coach' || turn.role === 'summary' || turn.role === 'supervisor') ? 'solid' : undefined}
              borderLeftColor={
                turn.role === 'coach' ? 'colorBorderDestructive' :
                turn.role === 'summary' ? 'colorBorderSuccess' :
                turn.role === 'supervisor' ? 'colorBorderWarning' :
                undefined
              }
            >
              <Text as="p" fontSize="fontSize20" fontWeight="fontWeightBold" marginBottom="space10">
                {turn.role === 'customer' ? 'Customer' :
                 turn.role === 'ai' ? 'AI Agent' :
                 turn.role === 'coach' ? 'Supervisor Prompt → AI Agent' :
                 turn.role === 'summary' ? 'Barge Summary (Supervisor ↔ Customer)' :
                 turn.role === 'supervisor' ? 'Supervisor (Live Voice)' :
                 'Unknown'}
              </Text>
              <Text as="p" fontSize={(turn.role === 'coach' || turn.role === 'supervisor') ? 'fontSize20' : 'fontSize30'}>
                {turn.content}
              </Text>
            </Box>
          </Box>
        ))}
        <div ref={bottomRef} />
      </Box>
    </Box>
  );
};
