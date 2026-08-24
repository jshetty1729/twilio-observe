import { describe, it, expect } from 'vitest';
import { csatService } from '../src/services/csat.service.js';

describe('CsatService', () => {
  it('starts at default score of 7', () => {
    csatService.initCall('CA-test-1');
    expect(csatService.getScore('CA-test-1')).toBe(7);
  });

  it('decreases score on negative customer message', () => {
    csatService.initCall('CA-test-2');
    csatService.scoreCustomerMessage('CA-test-2', "That's ridiculous, I can't believe this");
    expect(csatService.getScore('CA-test-2')).toBeLessThan(7);
  });

  it('increases score on positive customer message', () => {
    csatService.initCall('CA-test-3');
    csatService.scoreCustomerMessage('CA-test-3', 'That sounds good, thank you!');
    expect(csatService.getScore('CA-test-3')).toBeGreaterThan(7);
  });

  it('clamps score between 1 and 10', () => {
    csatService.initCall('CA-test-4');
    for (let i = 0; i < 20; i++) {
      csatService.scoreCustomerMessage('CA-test-4', 'This is ridiculous and unacceptable');
    }
    expect(csatService.getScore('CA-test-4')).toBeGreaterThanOrEqual(1);
    expect(csatService.getScore('CA-test-4')).toBeLessThanOrEqual(10);
  });

  it('decreases score when AI deflects', () => {
    csatService.initCall('CA-test-5');
    csatService.scoreAiResponse('CA-test-5', 'Our team will reach out within 3 to 5 business days');
    expect(csatService.getScore('CA-test-5')).toBeLessThan(7);
  });

  it('does not change score on neutral messages', () => {
    csatService.initCall('CA-test-6');
    csatService.scoreCustomerMessage('CA-test-6', 'I have a 2017 Keystone Cougar');
    expect(csatService.getScore('CA-test-6')).toBe(7);
  });
});
