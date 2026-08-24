import { config } from '../config.js';
import { logger } from '../utils/logger.js';
import { TranscriptTurn } from '../types/index.js';

interface GeminiMessage {
  role: 'user' | 'model';
  parts: Array<{ text: string }>;
}

export const geminiService = {
  async generateResponse(
    systemPrompt: string,
    conversationHistory: TranscriptTurn[],
    latestUserMessage: string
  ): Promise<string> {
    const contents: GeminiMessage[] = conversationHistory
      .filter(t => t.role !== 'supervisor')
      .map(turn => ({
        role: turn.role === 'customer' ? 'user' as const : 'model' as const,
        parts: [{ text: turn.content }],
      }));

    contents.push({
      role: 'user',
      parts: [{ text: latestUserMessage }],
    });

    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${config.gemini.apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: systemPrompt }] },
            contents,
            generationConfig: {
              maxOutputTokens: 150,
              temperature: 0.7,
            },
          }),
        }
      );

      if (!response.ok) {
        const err = await response.text();
        logger.error('Gemini API error', err);
        return "I'm sorry, I'm having a brief technical issue. Could you repeat that?";
      }

      const data = await response.json();
      const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!text) {
        logger.error('Gemini returned empty response', data);
        return "I apologize, could you say that again?";
      }

      return text.trim();
    } catch (error) {
      logger.error('Gemini request failed', error);
      return "I'm sorry, I'm experiencing a brief issue. One moment please.";
    }
  },
};
