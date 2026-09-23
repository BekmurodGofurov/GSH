import { describe, expect, it, vi, afterEach } from 'vitest';

import {
  formatEventBadge,
  formatPing,
  formatRelativeTime,
  formatTime,
  getPingBadgeColor,
  getPingColorClass,
} from '../utils/formatters';

describe('formatPing', () => {
  it('renders a number with one decimal and a unit', () => {
    expect(formatPing(38.46)).toBe('38.5 ms');
  });

  it('accepts a numeric string from the API', () => {
    expect(formatPing('42')).toBe('42.0 ms');
  });

  it('falls back to a placeholder for missing values', () => {
    expect(formatPing(null)).toBe('-- ms');
    expect(formatPing(undefined)).toBe('-- ms');
  });

  it('falls back to a placeholder for unparseable values', () => {
    expect(formatPing('fast')).toBe('-- ms');
  });

  it('does not treat zero as missing', () => {
    expect(formatPing(0)).toBe('0.0 ms');
  });
});

describe('getPingColorClass', () => {
  it.each([
    [10, 'emerald'],
    [29.9, 'emerald'],
    [30, 'cyan'],
    [74.9, 'cyan'],
    [75, 'amber'],
    [129.9, 'amber'],
    [130, 'rose'],
    [900, 'rose'],
  ])('maps %ims to the %s band', (ping, band) => {
    expect(getPingColorClass(ping)).toContain(band);
  });

  it('uses a neutral colour when there is no reading', () => {
    expect(getPingColorClass(null)).toBe('text-slate-400');
    expect(getPingColorClass(undefined)).toBe('text-slate-400');
  });
});

describe('getPingBadgeColor', () => {
  it.each([
    [10, 'emerald'],
    [50, 'cyan'],
    [100, 'amber'],
    [300, 'rose'],
  ])('maps %ims to the %s badge', (ping, band) => {
    expect(getPingBadgeColor(ping)).toContain(band);
  });

  it('uses a neutral badge when there is no reading', () => {
    expect(getPingBadgeColor(null)).toContain('slate');
  });

  it('always supplies a dark-mode variant', () => {
    expect(getPingBadgeColor(50)).toContain('dark:');
  });
});

describe('formatTime', () => {
  it('renders a placeholder for a missing timestamp', () => {
    expect(formatTime(null)).toBe('--:--:--');
    expect(formatTime('')).toBe('--:--:--');
  });

  it('renders a clock time for a valid ISO timestamp', () => {
    expect(formatTime('2026-01-01T12:34:56Z')).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});

describe('formatRelativeTime', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const now = new Date('2026-01-01T12:00:00Z');

  function ago(ms) {
    vi.useFakeTimers();
    vi.setSystemTime(now);
    return formatRelativeTime(new Date(now.getTime() - ms).toISOString());
  }

  it('says "Never" when there is no timestamp', () => {
    expect(formatRelativeTime(null)).toBe('Never');
  });

  it('collapses the last few seconds into "just now"', () => {
    expect(ago(2 * 1000)).toBe('just now');
  });

  it.each([
    [30 * 1000, '30s ago'],
    [5 * 60 * 1000, '5m ago'],
    [3 * 60 * 60 * 1000, '3h ago'],
    [2 * 24 * 60 * 60 * 1000, '2d ago'],
  ])('renders %ims as %s', (ms, expected) => {
    expect(ago(ms)).toBe(expected);
  });

  it('switches unit exactly at the minute boundary', () => {
    expect(ago(59 * 1000)).toBe('59s ago');
    expect(ago(60 * 1000)).toBe('1m ago');
  });
});

describe('formatEventBadge', () => {
  it.each([
    ['CRASH', 'CRASH', 'rose'],
    ['OFFLINE', 'OFFLINE', 'rose'],
    ['HIGH_PING', 'WARNING', 'amber'],
    ['WARNING', 'WARNING', 'amber'],
    ['RECOVERY', 'RECOVERY', 'emerald'],
  ])('maps %s to the %s badge', (eventType, label, variant) => {
    const badge = formatEventBadge(eventType);

    expect(badge.label).toBe(label);
    expect(badge.variant).toBe(variant);
  });

  it('is case insensitive', () => {
    expect(formatEventBadge('crash').label).toBe('CRASH');
  });

  it('passes an unknown event type through as its own label', () => {
    const badge = formatEventBadge('DDOS_ATTACK');

    expect(badge.label).toBe('DDOS_ATTACK');
    expect(badge.variant).toBe('cyan');
  });

  it('never returns an empty label', () => {
    expect(formatEventBadge(null).label).toBe('EVENT');
    expect(formatEventBadge('').label).toBe('EVENT');
  });

  it('always returns the full badge shape', () => {
    for (const type of ['CRASH', 'RECOVERY', 'SOMETHING_ELSE', null]) {
      expect(formatEventBadge(type)).toEqual({
        label: expect.any(String),
        variant: expect.any(String),
        dot: expect.any(String),
        badgeClass: expect.any(String),
      });
    }
  });
});
