import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MutedIndicator, isMuted } from '../components/common/MutedIndicator';
import { NotificationsDrawer } from '../components/common/NotificationsDrawer';

const FUTURE = new Date(Date.now() + 30 * 60 * 1000).toISOString();
const PAST = new Date(Date.now() - 30 * 60 * 1000).toISOString();

describe('MutedIndicator', () => {
  it('shows a mute icon while alerts are silenced', () => {
    render(<MutedIndicator server={{ muted_until: FUTURE }} />);

    expect(screen.getByTestId('muted-indicator')).toBeInTheDocument();
    expect(screen.getByLabelText(/Alerts muted until/i)).toBeInTheDocument();
  });

  it('renders nothing for a server that is not muted', () => {
    const { container } = render(<MutedIndicator server={{ muted_until: null }} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('treats a mute that has already run out as not muted', () => {
    expect(isMuted({ muted_until: PAST })).toBe(false);
    expect(isMuted({})).toBe(false);
    expect(isMuted(null)).toBe(false);
  });
});

describe('NotificationsDrawer', () => {
  it('is mounted on <body> and spans the full viewport height', () => {
    const { container } = render(
      <div>
        <NotificationsDrawer isOpen onClose={vi.fn()} notifications={[]} />
      </div>
    );

    // Not inside the page layout, where an ancestor can shrink `fixed`.
    expect(container.querySelector('.inset-y-0')).toBeNull();
    const drawer = document.body.querySelector('.fixed.inset-y-0.right-0');
    expect(drawer).not.toBeNull();
    expect(drawer.parentElement).toBe(document.body);
  });
});
