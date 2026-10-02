import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  api: {
    getServers: vi.fn(),
    probeAddress: vi.fn(),
    muteServer: vi.fn(),
    unmuteServer: vi.fn(),
  },
}));

import { AdminDashboardView } from '../components/views/AdminDashboardView';
import { api } from '../services/api';

const FUTURE = new Date(Date.now() + 60 * 60 * 1000).toISOString();
const SERVERS = [
  { server_id: '1.1.1.1:27015', server_name: 'Quiet', region: 'Vienna', status: 'ONLINE', muted_until: FUTURE },
  { server_id: '2.2.2.2:27015', server_name: 'Loud', region: 'Warsaw', status: 'ONLINE', muted_until: null },
];

describe('AdminDashboardView', () => {
  beforeEach(() => {
    Object.values(api).forEach((fn) => fn.mockReset());
    api.getServers.mockResolvedValue({ data: SERVERS, error: null });
  });

  it('shows the ping, players and capacity of a probed address', async () => {
    api.probeAddress.mockResolvedValue({
      data: { address: '9.9.9.9:27015', reachable: true, server_name: 'Probe Me', ping_ms: 41.6, player_count: 12, max_players: 24 },
      error: null,
    });
    const user = userEvent.setup();
    render(<AdminDashboardView />);

    await user.type(screen.getByLabelText(/Server address to check/i), '9.9.9.9');
    await user.click(screen.getByRole('button', { name: /Check Server/i }));

    const result = await screen.findByTestId('probe-result');
    expect(api.probeAddress).toHaveBeenCalledWith('9.9.9.9');
    expect(result).toHaveTextContent('Probe Me');
    expect(result).toHaveTextContent('42 ms');
    expect(result).toHaveTextContent('12');
    expect(result).toHaveTextContent('24');
    expect(result).toHaveTextContent('50%');
  });

  it('says so when the address does not answer', async () => {
    api.probeAddress.mockResolvedValue({ data: { address: '9.9.9.9:27015', reachable: false }, error: null });
    const user = userEvent.setup();
    render(<AdminDashboardView />);

    await user.type(screen.getByLabelText(/Server address to check/i), '9.9.9.9');
    await user.click(screen.getByRole('button', { name: /Check Server/i }));

    expect(await screen.findByText(/did not answer/i)).toBeInTheDocument();
  });

  it('shows the API error for a bad address', async () => {
    api.probeAddress.mockResolvedValue({ data: null, error: 'Enter an IP address or hostname' });
    const user = userEvent.setup();
    render(<AdminDashboardView />);

    await user.type(screen.getByLabelText(/Server address to check/i), 'nope');
    await user.click(screen.getByRole('button', { name: /Check Server/i }));

    expect(await screen.findByText(/Enter an IP address or hostname/)).toBeInTheDocument();
  });

  it('does not probe an empty box', () => {
    render(<AdminDashboardView />);

    expect(screen.getByRole('button', { name: /Check Server/i })).toBeDisabled();
  });

  it('flags a muted server and offers Unmute only for it', async () => {
    render(<AdminDashboardView />);

    await screen.findByText('Quiet');
    expect(screen.getAllByTestId('muted-indicator')).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /^Unmute$/ })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /^Mute$/ })).toHaveLength(1);
  });

  it('mutes a server for the chosen time', async () => {
    api.muteServer.mockResolvedValue({ data: { status: 'muted' }, error: null });
    const user = userEvent.setup();
    render(<AdminDashboardView />);

    await screen.findByText('Loud');
    await user.click(screen.getByRole('button', { name: /^Mute$/ }));
    await user.click(screen.getByRole('button', { name: /Mute Alerts/i }));

    expect(api.muteServer).toHaveBeenCalledWith('2.2.2.2:27015', 30, 'Muted from admin console');
  });

  it('unmutes a muted server', async () => {
    api.unmuteServer.mockResolvedValue({ data: { status: 'unmuted' }, error: null });
    const user = userEvent.setup();
    render(<AdminDashboardView />);

    await screen.findByText('Quiet');
    await user.click(screen.getByRole('button', { name: /^Unmute$/ }));

    expect(api.unmuteServer).toHaveBeenCalledWith('1.1.1.1:27015');
  });
});
