import React, { useState } from 'react';
import { Box, Heading, Button, Text, Stack } from '@twilio-paste/core';
import { api } from '../services/api';

interface BargeControlsProps {
  callSid: string;
  status: string;
}

export const BargeControls: React.FC<BargeControlsProps> = ({ callSid, status }) => {
  const [barging, setBarging] = useState(false);

  const isBarged = status === 'barged';

  const handleBarge = async () => {
    setBarging(true);
    try {
      await api.initiateBarge(callSid);
    } catch (error) {
      console.error('Barge failed:', error);
      setBarging(false);
    }
  };

  const handleHandBack = async () => {
    await api.handBack(callSid);
    setBarging(false);
  };

  return (
    <Box>
      <Box marginBottom="space30">
        <Heading as="h3" variant="heading30">
          Barge Controls
        </Heading>
      </Box>

      {!isBarged ? (
        <Box>
          <Text as="p" marginBottom="space30" color="colorTextWeak">
            Take over when the AI is stuck or damaging the customer relationship.
          </Text>
          <Button
            variant="destructive"
            onClick={handleBarge}
            loading={barging}
          >
            Barge Into Call
          </Button>
        </Box>
      ) : (
        <Stack orientation="vertical" spacing="space30">
          <Text as="p" fontWeight="fontWeightBold" color="colorTextError">
            LIVE — AI is in silent co-pilot mode.
          </Text>
          <Button variant="primary" onClick={handleHandBack}>
            Hand Back to AI
          </Button>
        </Stack>
      )}
    </Box>
  );
};
