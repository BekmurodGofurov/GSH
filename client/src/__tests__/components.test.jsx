import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { Badge } from '../components/common/Badge';
import { ConnectionBanner } from '../components/common/ConnectionBanner';
import { cn } from '../utils/cn';

describe('cn', () => {
  it('joins class names', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('drops falsy entries', () => {
    expect(cn('a', false, null, undefined, 'b')).toBe('a b');
  });

  it('lets the last conflicting tailwind class win', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });
});

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>ONLINE</Badge>);

    expect(screen.getByText('ONLINE')).toBeInTheDocument();
  });

  it('falls back to the neutral variant for an unknown one', () => {
    render(<Badge variant="chartreuse">X</Badge>);

    expect(screen.getByText('X').className).toContain('slate');
  });

  it('applies the requested variant', () => {
    render(<Badge variant="rose">CRASH</Badge>);

    expect(screen.getByText('CRASH').className).toContain('rose');
  });

  it('forwards extra props to the underlying element', () => {
    render(<Badge data-testid="badge" title="tooltip">X</Badge>);

    expect(screen.getByTestId('badge')).toHaveAttribute('title', 'tooltip');
  });
});

describe('ConnectionBanner', () => {
  it('renders nothing while the connection is healthy', () => {
    const { container } = render(<ConnectionBanner isOffline={false} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('warns when the gateway is unreachable', () => {
    render(<ConnectionBanner isOffline wsStatus="disconnected" retryCountdown={5} />);

    expect(screen.getByText(/OFFLINE MODE/)).toBeInTheDocument();
    expect(screen.getByText(/5/)).toBeInTheDocument();
  });

  it('confirms recovery even when still flagged offline', () => {
    render(<ConnectionBanner isOffline justReconnected />);

    expect(screen.getByText(/LIVE TELEMETRY RESTORED/)).toBeInTheDocument();
    expect(screen.queryByText(/OFFLINE MODE/)).not.toBeInTheDocument();
  });

  it('lets the user retry on demand', async () => {
    const onRetry = vi.fn();
    render(<ConnectionBanner isOffline retryCountdown={0} onRetry={onRetry} />);

    await userEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledOnce();
  });
});
