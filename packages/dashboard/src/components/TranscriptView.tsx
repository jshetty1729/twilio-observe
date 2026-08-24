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
            justifyContent={turn.role === 'ai' ? 'flex-end' : 'flex-start'}
            marginBottom="space30"
          >
            <Box
              backgroundColor={
                turn.role === 'customer' ? 'colorBackgroundPrimaryWeakest' :
                turn.role === 'ai' ? 'colorBackgroundSuccessWeakest' :
                'colorBackgroundWarningWeakest'
              }
              padding="space30"
              borderRadius="borderRadius20"
              maxWidth="70%"
            >
              <Text as="p" fontSize="fontSize20" fontWeight="fontWeightBold" marginBottom="space10">
                {turn.role === 'customer' ? 'Customer' : turn.role === 'ai' ? 'AI Agent' : 'Supervisor'}
              </Text>
              <Text as="p" fontSize="fontSize30">{turn.content}</Text>
            </Box>
          </Box>
        ))}
        <div ref={bottomRef} />
      </Box>
    </Box>
  );
};
