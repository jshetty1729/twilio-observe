import React from 'react';
import { Box, Text } from '@twilio-paste/core';

interface CsatIndicatorProps {
  score: number;
}

export const CsatIndicator: React.FC<CsatIndicatorProps> = ({ score }) => {
  const getColor = () => {
    if (score >= 7) return 'colorTextSuccess' as const;
    if (score >= 4) return 'colorTextWarning' as const;
    return 'colorTextError' as const;
  };

  return (
    <Box display="flex" alignItems="center" columnGap="space20">
      <Text as="span" fontSize="fontSize60" fontWeight="fontWeightBold" color={getColor()}>
        {score}
      </Text>
      <Text as="span" color="colorTextWeak">/10 CSAT</Text>
    </Box>
  );
};
