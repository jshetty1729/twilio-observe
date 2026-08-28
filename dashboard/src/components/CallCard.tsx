import React from 'react';
import { Box, Text, Badge } from '@twilio-paste/core';
import { ActiveCall } from '../types';
import { CsatIndicator } from './CsatIndicator';

const SentimentBadge: React.FC<{ sentiment: string }> = ({ sentiment }) => {
  const variant = (() => {
    const s = sentiment.toLowerCase();
    if (['negative', 'very_negative', 'frustrated', 'angry'].includes(s)) return 'error' as const;
    if (['positive', 'very_positive', 'satisfied'].includes(s)) return 'success' as const;
    return 'neutral' as const;
  })();
  return <Badge as="span" variant={variant}>{sentiment}</Badge>;
};

interface CallCardProps {
  call: ActiveCall;
  onClick: (callSid: string) => void;
}

export const CallCard: React.FC<CallCardProps> = ({ call, onClick }) => {
  const duration = Math.floor((Date.now() - call.startTime) / 1000);
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;

  return (
    <Box
      padding="space40"
      borderWidth="borderWidth10"
      borderStyle="solid"
      borderColor="colorBorderWeak"
      borderRadius="borderRadius20"
      cursor="pointer"
      onClick={() => onClick(call.callSid)}
      _hover={{ backgroundColor: 'colorBackgroundPrimaryWeakest' }}
    >
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Text as="p" fontWeight="fontWeightBold">{call.callerNumber || 'Unknown Caller'}</Text>
          <Text as="p" color="colorTextWeak" fontSize="fontSize20">
            {minutes}:{seconds.toString().padStart(2, '0')} | {(call.callSid || '').slice(0, 10)}...
          </Text>
        </Box>
        <Box display="flex" alignItems="center" columnGap="space30">
          <CsatIndicator score={call.csat} />
          <SentimentBadge sentiment={call.sentiment} />
        </Box>
      </Box>
      {call.topic && (
        <Box marginTop="space20">
          <Badge as="span" variant="info">{call.topic}</Badge>
        </Box>
      )}
      {call.status !== 'active' && (
        <Box marginTop="space20">
          <Badge as="span" variant={call.status === 'barged' ? 'error' : 'warning'}>
            {call.status.toUpperCase()}
          </Badge>
        </Box>
      )}
    </Box>
  );
};
