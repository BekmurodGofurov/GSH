import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// The panel pulls in the LiveKit components, which open a real WebSocket
// and reach for getUserMedia the moment a room renders. jsdom has
// neither, so the room and its hooks are stubbed: these tests are about
// the one shared conversation, not about LiveKit's internals.
vi.mock('@livekit/components-styles', () => ({}));
vi.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children, options }) => (
    <div data-testid="livekit-room" data-stop-mic-on-mute={String(options?.publishDefaults?.stopMicTrackOnMute)}>
      {children}
    </div>
  ),
  RoomAudioRenderer: () => null,
  // Stood up the way the real one renders: a plain <button> with the
  // caller's props spread onto it and no type of its own. Inside a <form>
  // that defaults to submit, so this stub is what keeps the panel honest
  // about where the voice controls sit.
  StartAudio: ({ label, ...props }) => <button {...props}>{label}</button>,
  BarVisualizer: () => null,
  useVoiceAssistant: () => ({ state: 'listening', audioTrack: null, error: null }),
  useConnectionState: () => 'connected',
  useLocalParticipant: () => ({ localParticipant: null, isMicrophoneEnabled: true }),
  useDataChannel: (cb) => {
    globalThis.__dataChannelHandler = cb;
    return {};
  },
  useRoomContext: () => null,
}));
vi.mock('livekit-client', () => ({ ConnectionState: { Connected: 'connected' } }));

vi.mock('../services/api', () => ({
  api: {
    askAgent: vi.fn(),
    getLivekitToken: vi.fn(),
  },
}));

import { AskPanel } from '../components/common/AskPanel';
import { api } from '../services/api';

function renderPanel() {
  return render(<AskPanel isOpen onOpen={() => {}} onClose={() => {}} />);
}

describe('AskPanel', () => {
  beforeEach(() => {
    api.askAgent.mockReset();
    api.getLivekitToken.mockReset();
  });

  it('offers typing and talking in one place, with no mode to pick first', () => {
    renderPanel();

    // One composer, carrying both ways in.
    expect(screen.getByPlaceholderText(/Ask about servers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Start voice session/i)).toBeInTheDocument();
    // The old Text / Voice tab switch is gone.
    expect(screen.queryByRole('button', { name: /^Text$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Voice$/ })).not.toBeInTheDocument();
  });

  it('shows the answer to a typed question in the conversation', async () => {
    api.askAgent.mockResolvedValue({
      data: { answer: 'There are 45 players across 23 online servers.', tool_used: 'get_fleet_overview', chart: null },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'How many players are online?{Enter}');

    expect(await screen.findByText(/45 players across 23 online servers/)).toBeInTheDocument();
    expect(screen.getByText('get_fleet_overview')).toBeInTheDocument();
  });

  it('draws no chart for a counting answer', async () => {
    api.askAgent.mockResolvedValue({
      data: { answer: 'There are 23 servers, all online.', tool_used: 'get_fleet_overview', chart: null },
      error: null,
    });
    const user = userEvent.setup();
    const { container } = renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'How many servers are online?{Enter}');
    await screen.findByText(/23 servers, all online/);

    expect(container.querySelector('svg')).toBeNull();
  });

  it('draws the chart under a ranking answer, in the ranking order', async () => {
    api.askAgent.mockResolvedValue({
      data: {
        answer: 'Solid is the best server right now.',
        tool_used: 'get_server_ranking',
        chart: {
          chartType: 'bar',
          title: 'Average ping over 1h — best first',
          unit: 'ms',
          rows: [
            { label: 'Solid', value: 60, status: 'ONLINE', note: null },
            { label: 'Flaky', value: 25, status: 'ONLINE', note: '2 crash(es)' },
          ],
        },
      },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), "What's the best server?{Enter}");

    await screen.findByText(/Solid is the best server/);
    expect(screen.getByText(/Average ping over 1h/i)).toBeInTheDocument();
    // The crash count sits beside the bar, so a taller winning bar still reads
    // correctly against the answer.
    expect(screen.getByText('2 crash(es)')).toBeInTheDocument();
  });

  it('draws exactly the servers asked for and sets the winner apart', async () => {
    const rows = Array.from({ length: 12 }, (_, i) => ({
      label: `Server ${i + 1}`,
      value: 20 + i,
      status: 'ONLINE',
      note: null,
      highlight: i === 0,
    }));
    api.askAgent.mockResolvedValue({
      data: {
        answer: 'Here are the top 12.',
        tool_used: 'get_server_ranking',
        chart: { chartType: 'bar', title: '12 best servers · average ping over 1h', order: 'best', unit: 'ms', rows },
      },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'top 12 servers{Enter}');
    await screen.findByText(/Here are the top 12/);

    // No silent cap: all twelve bars are there, and only the first is starred.
    // (the panel is portalled to <body>, so query there, not the render container)
    expect(document.body.querySelectorAll('svg[role="img"] rect')).toHaveLength(12);
    expect(screen.getAllByText(/★/)).toHaveLength(1);
    expect(screen.getByText(/★ Server 1/)).toBeInTheDocument();
  });

  it('draws every server in an overview chart, offline ones marked', async () => {
    const rows = [
      ...Array.from({ length: 21 }, (_, i) => ({ label: `S${i + 1}`, value: 20 + i, status: 'ONLINE' })),
      { label: 'Down A', value: 0, status: 'OFFLINE', note: 'offline' },
      { label: 'Down B', value: 0, status: 'OFFLINE', note: 'offline' },
    ];
    api.askAgent.mockResolvedValue({
      data: {
        answer: 'There are 23 servers: 21 online and 2 offline.',
        tool_used: 'get_servers_overview',
        chart: { chartType: 'bar', title: 'All 23 servers · 21 online · 2 offline', order: 'overview', unit: 'ms', rows },
      },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'show me all servers{Enter}');

    await screen.findByText(/21 online and 2 offline/);
    expect(document.body.querySelectorAll('svg[role="img"] rect')).toHaveLength(23);
    expect(screen.getAllByText('OFFLINE')).toHaveLength(2);
  });

  it('marks a worst-servers chart as such', async () => {
    api.askAgent.mockResolvedValue({
      data: {
        answer: 'The 2 worst servers.',
        tool_used: 'get_server_ranking',
        chart: {
          chartType: 'bar',
          title: '2 worst servers · average ping over 1h',
          order: 'worst',
          unit: 'ms',
          rows: [
            { label: 'Bad', value: 200, highlight: true },
            { label: 'Meh', value: 120, highlight: false },
          ],
        },
      },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'worst 2{Enter}');

    expect(await screen.findByText(/2 worst servers · average ping/)).toBeInTheDocument();
    expect(screen.getByText(/★ Bad/)).toBeInTheDocument();
  });

  it('is themed for light mode as well as dark', () => {
    renderPanel();
    const panel = document.body.querySelector('.fixed.inset-y-0.right-0');

    // Every dark surface carries a light counterpart rather than being
    // dark-only.
    expect(panel.className).toMatch(/bg-slate-50/);
    expect(panel.className).toMatch(/dark:bg-\[#080e1a\]/);
    expect(panel.innerHTML).not.toMatch(/class="[^"]*(^|\s)bg-\[#080e1a\]/);
  });

  it('keeps the typed conversation when a voice session starts', async () => {
    api.askAgent.mockResolvedValue({
      data: { answer: 'All 23 servers are online.', tool_used: 'get_fleet_overview', chart: null },
      error: null,
    });
    api.getLivekitToken.mockResolvedValue({
      data: { token: 'test-token', url: 'wss://test.livekit.cloud' },
      error: null,
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'Status?{Enter}');
    await screen.findByText(/All 23 servers are online/);

    await user.click(screen.getByLabelText(/Start voice session/i));

    // One thread: switching to voice does not clear what was typed, and
    // the text box stays available while the mic is live.
    await screen.findByTestId('livekit-room');
    expect(screen.getByText(/All 23 servers are online/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask about servers/i)).toBeInTheDocument();
  });

  it('lets go of the microphone when it is muted, not just silences it', async () => {
    api.getLivekitToken.mockResolvedValue({ data: { token: 't', url: 'wss://x' }, error: null });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText(/Start voice session/i));

    const room = await screen.findByTestId('livekit-room');
    expect(room).toHaveAttribute('data-stop-mic-on-mute', 'true');
  });

  it('hangs up when the assistant is told to stop', async () => {
    api.getLivekitToken.mockResolvedValue({ data: { token: 't', url: 'wss://x' }, error: null });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText(/Start voice session/i));
    await screen.findByTestId('livekit-room');

    act(() => {
      globalThis.__dataChannelHandler({ payload: new TextEncoder().encode(JSON.stringify({ type: 'stop' })) });
    });

    await waitFor(() => expect(screen.queryByTestId('livekit-room')).not.toBeInTheDocument());
  });

  it('has an End button that closes the voice session', async () => {
    api.getLivekitToken.mockResolvedValue({ data: { token: 't', url: 'wss://x' }, error: null });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText(/Start voice session/i));
    await screen.findByTestId('livekit-room');
    await user.click(screen.getByLabelText(/End voice session/i));

    expect(screen.queryByTestId('livekit-room')).not.toBeInTheDocument();
  });

  it('does not send a half-typed question when audio is enabled', async () => {
    api.getLivekitToken.mockResolvedValue({
      data: { token: 'test-token', url: 'wss://test.livekit.cloud' },
      error: null,
    });
    api.askAgent.mockResolvedValue({ data: { answer: 'ok', tool_used: null, chart: null }, error: null });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText(/Start voice session/i));
    await screen.findByTestId('livekit-room');

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'half a thought');
    await user.click(screen.getByText('Enable audio'));

    // LiveKit's buttons carry no `type`, so one inside the form would
    // count as a submit and fire the draft off as a question.
    expect(api.askAgent).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText(/Ask about servers/i)).toHaveValue('half a thought');
  });

  it('surfaces a failed voice handshake without losing the chat', async () => {
    api.getLivekitToken.mockResolvedValue({ data: null, error: 'LiveKit is not configured on this server.' });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText(/Start voice session/i));

    expect(await screen.findByText(/LiveKit is not configured/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask about servers/i)).toBeInTheDocument();
  });

  it('shows an agent error as an error bubble', async () => {
    api.askAgent.mockResolvedValue({ data: null, error: 'Request timed out' });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByPlaceholderText(/Ask about servers/i), 'Status?{Enter}');

    expect(await screen.findByText(/Request timed out/)).toBeInTheDocument();
  });

  it('sends a suggested question when one is clicked', async () => {
    api.askAgent.mockResolvedValue({ data: { answer: 'ok', tool_used: null, chart: null }, error: null });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByText('Which server is performing best, and why?'));

    await waitFor(() =>
      expect(api.askAgent).toHaveBeenCalledWith('Which server is performing best, and why?')
    );
  });
});
