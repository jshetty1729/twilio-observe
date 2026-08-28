import React, { useState, useRef, useCallback } from 'react';
import { Box, Heading, Button, Text, Stack } from '@twilio-paste/core';
import { Device, Call } from '@twilio/voice-sdk';
import { api } from '../services/api';

interface BargeControlsProps {
  callSid: string;
  status: string;
}

export const BargeControls: React.FC<BargeControlsProps> = ({ callSid, status }) => {
  const [barging, setBarging] = useState(false);
  const [connected, setConnected] = useState(false);
  const [handingBack, setHandingBack] = useState(false);
  const deviceRef = useRef<Device | null>(null);
  const callRef = useRef<Call | null>(null);
  const confNameRef = useRef<string>('');

  const isBarged = status === 'barged';
  const canHandBack = isBarged && !handingBack;

  const handleBarge = async () => {
    setBarging(true);
    try {
      const result = await api.initiateBarge(callSid);
      const { token, conf_name } = result;
      confNameRef.current = conf_name;

      // Connect supervisor to conference via Voice JS SDK
      const device = new Device(token, { edge: 'ashburn' });
      deviceRef.current = device;

      await device.register();

      // Call out to the conference via TwiML App
      const call = await device.connect({
        params: { conf_name },
      });

      call.on('accept', () => setConnected(true));
      call.on('disconnect', () => {
        setConnected(false);
        setBarging(false);
      });

      callRef.current = call;
    } catch (error) {
      console.error('Barge failed:', error);
      setBarging(false);
    }
  };

  const handleHandBack = useCallback(async () => {
    setHandingBack(true);
    try {
      // Disconnect supervisor from conference
      if (callRef.current) {
        callRef.current.disconnect();
        callRef.current = null;
      }
      if (deviceRef.current) {
        deviceRef.current.destroy();
        deviceRef.current = null;
      }

      // Tell server to redirect customer back to ConversationRelay
      await api.handBack(callSid);
      setConnected(false);
      setBarging(false);
    } catch (error) {
      console.error('Hand-back failed:', error);
    } finally {
      setHandingBack(false);
    }
  }, [callSid]);

  return (
    <Box>
      <Box marginBottom="space30">
        <Heading as="h3" variant="heading30">
          Barge Controls
        </Heading>
      </Box>

      {!isBarged && !barging ? (
        <Box>
          <Text as="p" marginBottom="space30" color="colorTextWeak">
            Take over the call — your mic connects directly to the customer.
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
            {connected ? 'LIVE — You are speaking directly to the customer.' : 'Supervisor is on the call.'}
          </Text>
          {connected && (
            <Text as="p" fontSize="fontSize20" color="colorTextWeak">
              Your microphone is active. The customer can hear you.
            </Text>
          )}
          <Button
            variant="primary"
            onClick={handleHandBack}
            loading={handingBack}
            disabled={!canHandBack}
          >
            Hand Back to AI
          </Button>
        </Stack>
      )}
    </Box>
  );
};
