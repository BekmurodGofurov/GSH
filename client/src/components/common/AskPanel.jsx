import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { X, Bot, Send, Loader2, Wrench, AlertTriangle, Mic, MicOff, MessageSquare } from 'lucide-react';
import { api } from '../../services/api';
import '@livekit/components-styles';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  useVoiceAssistant,
  BarVisualizer,
  useConnectionState,
  useLocalParticipant,
  useDataChannel,
  useRoomContext,
} from '@livekit/components-react';
import { ConnectionState, RoomEvent } from 'livekit-client';

const MAX_INPUT_HEIGHT = 180;
const INACTIVITY_TIMEOUT_S = 60;

// ─── Inline bar chart (pure SVG, no external dependencies) ───────────────────
function BarChart({ title, rows }) {
  if (!rows || rows.length === 0) return null;
  const max = Math.max(...rows.map((r) => r.value || 0), 1);
  const BAR_H = 18;
  const GAP = 6;
  const LABEL_W = 130;
  const BAR_MAX_W = 160;
  const svgH = rows.length * (BAR_H + GAP) + 4;

  return (
    <div className="my-2 rounded-xl border border-cyan-800/40 bg-slate-900/90 px-3 pt-3 pb-2 backdrop-blur-sm">
      <p className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider mb-2">{title}</p>
      <svg width={LABEL_W + BAR_MAX_W + 48} height={svgH} className="overflow-visible">
        {rows.map((row, i) => {
          const y = i * (BAR_H + GAP);
          const barW = max > 0 ? Math.round((row.value / max) * BAR_MAX_W) : 4;
          const isOnline = row.status === 'ONLINE';
          const barColor = isOnline ? '#22d3ee' : '#f87171';
          return (
            <g key={i}>
              <text
                x={LABEL_W - 6}
                y={y + BAR_H / 2 + 4}
                textAnchor="end"
                fontSize="9"
                fill="#94a3b8"
                fontFamily="monospace"
              >
                {row.label}
              </text>
              <rect
                x={LABEL_W}
                y={y + 2}
                width={Math.max(barW, 4)}
                height={BAR_H - 4}
                rx={3}
                fill={barColor}
                fillOpacity={0.8}
              />
              <text
                x={LABEL_W + Math.max(barW, 4) + 5}
                y={y + BAR_H / 2 + 4}
                fontSize="9"
                fill="#e2e8f0"
                fontFamily="monospace"
              >
                {row.value}ms
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Unmistakable Mic Button ─────────────────────────────────────────────────
function AnimatedMicButton({ voiceState, isMicrophoneEnabled, onToggle }) {
  const isMuted = !isMicrophoneEnabled;
  const isListening = voiceState === 'listening';
  const isSpeaking = voiceState === 'speaking';
  const showRings = !isMuted && (isListening || isSpeaking);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative flex items-center justify-center">
        {showRings && isListening && (
          <>
            <span className="absolute w-20 h-20 rounded-full bg-cyan-500/20 animate-ping" style={{ animationDuration: '1.4s' }} />
            <span className="absolute w-16 h-16 rounded-full bg-cyan-500/25 animate-ping" style={{ animationDuration: '1s' }} />
          </>
        )}
        {showRings && isSpeaking && (
          <span className="absolute w-20 h-20 rounded-full bg-violet-500/20 animate-ping" style={{ animationDuration: '1.2s' }} />
        )}

        <button
          type="button"
          onClick={onToggle}
          title={isMuted ? 'Microphone is muted — click to unmute' : 'Microphone is active — click to mute'}
          aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
          className={`
            relative z-10 flex items-center justify-center w-14 h-14 rounded-full
            border-2 transition-all duration-200 select-none focus:outline-none
            active:scale-95 cursor-pointer
            ${isMuted
              ? 'bg-slate-900 border-rose-500 text-rose-400 hover:bg-slate-800 shadow-[0_0_12px_rgba(244,63,94,0.25)]'
              : isSpeaking
                ? 'bg-violet-600 border-violet-400 text-white shadow-[0_0_24px_rgba(139,92,246,0.5)]'
                : 'bg-cyan-600 border-cyan-400 text-white shadow-[0_0_24px_rgba(6,182,212,0.5)]'
            }
          `}
        >
          {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
        </button>
      </div>

      <div className="flex flex-col items-center gap-1 text-center select-none">
        <span
          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase border ${
            isMuted
              ? 'bg-rose-950/80 text-rose-300 border-rose-800'
              : 'bg-cyan-950/80 text-cyan-300 border-cyan-800'
          }`}
        >
          {isMuted ? 'Muted' : 'Mic Active'}
        </span>
        <span className="text-[11px] font-mono text-slate-400">
          {isMuted
            ? 'Click to unmute'
            : isSpeaking
              ? 'GSH speaking…'
              : isListening
                ? 'Listening to you…'
                : 'Ready — speak now'}
        </span>
      </div>
    </div>
  );
}

// ─── Voice Tab with Real-time Streamed Transcript ────────────────────────────
function VoiceTab({ onDisconnect }) {
  const { state, audioTrack } = useVoiceAssistant();
  const connectionState = useConnectionState();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const room = useRoomContext();
  const transcriptEndRef = useRef(null);
  const inactivityTimerRef = useRef(null);

  // Unified items list: { id, role: 'user' | 'agent' | 'chart', text, final, chart, time }
  const [items, setItems] = useState([]);

  const toggleMic = useCallback(async () => {
    if (localParticipant) {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
    }
  }, [localParticipant, isMicrophoneEnabled]);

  // 1. Data Channel: exclusively for real-time visual charts
  useDataChannel((msg) => {
    try {
      const decoded = new TextDecoder().decode(msg.payload);
      const data = JSON.parse(decoded);

      if (data.type === 'chart') {
        setItems((prev) => {
          // Avoid duplicate chart cards if sent multiple times
          const recentChart = prev.slice(-2).find((m) => m.role === 'chart' && m.chart?.title === data.title);
          if (recentChart) return prev;
          return [
            ...prev,
            {
              id: `chart_${Date.now()}`,
              role: 'chart',
              chart: data,
              time: Date.now(),
            },
          ];
        });
      }
    } catch {
      // not a json payload
    }
  });

  // 2. Single LiveKit 2.x TextStream handler for speech chunks with in-place turn updates & noise filtering
  useEffect(() => {
    if (!room) return;

    const handleTextStream = async (stream, { identity }) => {
      const isUser =
        stream.info?.attributes?.['lk.publish_on_behalf'] === localParticipant?.identity ||
        identity === localParticipant?.identity;
      const role = isUser ? 'user' : 'agent';
      const streamId = stream.info?.id || `${role}_${Date.now()}`;
      let accumulated = '';

      try {
        for await (const chunk of stream) {
          accumulated += chunk;
          const cleanText = accumulated.trim();

          // Noise filter: discard if text contains no alphanumeric characters (e.g. ".", "...", " ")
          if (!/[a-zA-Z0-9]/.test(cleanText)) {
            continue;
          }

          setItems((prev) => {
            const list = [...prev];
            const idx = list.findIndex((m) => m.id === streamId);

            if (idx >= 0) {
              list[idx] = { ...list[idx], text: cleanText, final: false };
              return list;
            }

            // If the last message is from the same speaker and either not final or a continuation within 3s
            const last = list[list.length - 1];
            if (
              last &&
              last.role === role &&
              (!last.final || (Date.now() - (last.time || 0) < 3000 && cleanText.startsWith(last.text)))
            ) {
              list[list.length - 1] = { ...last, id: streamId, text: cleanText, final: false };
              return list;
            }

            // Deduplicate: avoid pushing identical text if already present in recent items
            const isDup = list.slice(-2).some((m) => m.role === role && m.text === cleanText);
            if (isDup) {
              return list;
            }

            list.push({
              id: streamId,
              role,
              text: cleanText,
              final: false,
              time: Date.now(),
            });
            return list;
          });
        }
      } catch {
        // Stream aborted or closed
      }

      const finalClean = accumulated.trim();
      setItems((prev) => {
        if (!/[a-zA-Z0-9]/.test(finalClean)) {
          // Remove noise bubble if any was added
          return prev.filter((m) => m.id !== streamId);
        }
        const list = [...prev];
        const idx = list.findIndex((m) => m.id === streamId);
        if (idx >= 0) {
          list[idx] = { ...list[idx], text: finalClean, final: true };
        }
        return list;
      });
    };

    try {
      room.registerTextStreamHandler('lk.transcription', handleTextStream);
    } catch {
      // Handler already registered
    }

    return () => {
      try {
        room.unregisterTextStreamHandler('lk.transcription');
      } catch {}
    };
  }, [room, localParticipant]);

  // Auto-disconnect on silence
  useEffect(() => {
    const active = state === 'speaking' || state === 'listening';
    clearTimeout(inactivityTimerRef.current);
    if (!active) {
      inactivityTimerRef.current = setTimeout(onDisconnect, INACTIVITY_TIMEOUT_S * 1000);
    }
    return () => clearTimeout(inactivityTimerRef.current);
  }, [state, onDisconnect]);

  // Auto-scroll
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [items]);

  const isConnected = connectionState === ConnectionState.Connected;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#080e1a]">
      <div className="flex justify-center pt-3 shrink-0">
        <StartAudio
          label="Tap to enable audio"
          className="px-3 py-1 bg-cyan-600/80 hover:bg-cyan-600 text-white rounded-full text-[11px] font-semibold transition-colors"
        />
      </div>

      <div className="shrink-0 px-8 pt-2">
        <BarVisualizer state={state} trackRef={audioTrack} className="w-full h-8" />
      </div>

      <div className="flex-1 overflow-y-auto mx-4 my-3 rounded-2xl border border-slate-800/60 bg-slate-900/40 p-3 space-y-2.5 min-h-0">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2.5 py-8 text-center">
            <div className="w-9 h-9 rounded-full border border-slate-700 flex items-center justify-center">
              <Mic className="w-4 h-4 text-slate-500" />
            </div>
            <p className="text-xs text-slate-500 max-w-[200px] leading-relaxed">
              {isConnected
                ? isMicrophoneEnabled
                  ? 'Speak now. GSH will answer with voice and diagrams.'
                  : 'Microphone is muted. Unmute below to speak.'
                : 'Connecting to voice session…'}
            </p>
          </div>
        ) : (
          items.map((item) => {
            if (item.role === 'chart') {
              return <BarChart key={item.id} title={item.chart.title} rows={item.chart.rows} />;
            }
            const isUser = item.role === 'user';
            return (
              <div key={item.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] px-3.5 py-2 text-xs leading-relaxed ${
                    isUser
                      ? 'bg-slate-700/80 text-slate-100 rounded-2xl rounded-br-sm'
                      : 'bg-gradient-to-br from-cyan-900/50 to-slate-900/60 text-cyan-100 border border-cyan-800/30 rounded-2xl rounded-bl-sm'
                  } ${!item.final ? 'opacity-80' : 'opacity-100'}`}
                >
                  <span className={`block text-[10px] font-bold mb-0.5 ${isUser ? 'text-slate-400' : 'text-cyan-500'}`}>
                    {isUser ? 'You' : 'GSH'}
                    {!item.final && <span className="ml-1 text-[9px] font-normal italic opacity-70">speaking…</span>}
                  </span>
                  {item.text}
                </div>
              </div>
            );
          })
        )}
        <div ref={transcriptEndRef} />
      </div>

      <div className="shrink-0 flex justify-center pb-8 pt-3">
        <AnimatedMicButton
          voiceState={state}
          isMicrophoneEnabled={isMicrophoneEnabled}
          onToggle={toggleMic}
        />
      </div>
    </div>
  );
}

// ─── Main Panel Container ────────────────────────────────────────────────────
export function AskPanel({ isOpen, onOpen, onClose }) {
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);
  const [mode, setMode] = useState('text');
  const [lkSession, setLkSession] = useState(null);
  const [lkConnecting, setLkConnecting] = useState(false);
  const [lkError, setLkError] = useState(null);

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const startVoice = async () => {
    setLkConnecting(true);
    setLkError(null);
    const { data, error: err } = await api.getLivekitToken();
    setLkConnecting(false);
    if (err || !data) {
      setLkError(err || 'Could not get voice session token.');
      return;
    }
    setLkSession({ token: data.token, url: data.url });
  };

  const stopVoice = useCallback(() => {
    setLkSession(null);
    setLkError(null);
  }, []);

  const handleClose = useCallback(() => {
    stopVoice();
    onClose();
  }, [onClose, stopVoice]);

  const resizeInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const needed = el.scrollHeight;
    el.style.height = `${Math.min(needed, MAX_INPUT_HEIGHT)}px`;
    el.style.overflowY = needed > MAX_INPUT_HEIGHT ? 'auto' : 'hidden';
  }, []);

  useEffect(resizeInput, [question, resizeInput]);

  useEffect(() => {
    if (isOpen && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 300);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, handleClose]);

  async function handleSubmit(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || isLoading) return;
    setIsLoading(true);
    setResponse(null);
    setError(null);
    const { data, error: err } = await api.askAgent(q);
    setIsLoading(false);
    if (err) {
      setError(err);
    } else {
      setResponse(data);
    }
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit(e);
  }

  return createPortal(
    <>
      <button
        type="button"
        onClick={onOpen}
        title="Ask the Agent"
        aria-label="Ask the Agent"
        className={`fixed right-5 bottom-20 md:bottom-6 z-40 flex items-center justify-center w-14 h-14 rounded-full bg-cyan-600 hover:bg-cyan-700 text-white shadow-lg shadow-cyan-900/30 ring-1 ring-cyan-400/40 transition-all duration-200 ${
          isOpen ? 'opacity-0 pointer-events-none scale-90' : 'opacity-100 scale-100'
        }`}
      >
        <Bot className="w-6 h-6" />
      </button>

      <div
        onClick={handleClose}
        aria-hidden={!isOpen}
        className={`fixed inset-0 z-40 bg-slate-950/30 dark:bg-slate-950/50 backdrop-blur-[2px] transition-opacity duration-300 ease-in-out ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />

      <div
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[560px] lg:w-[680px] xl:w-[760px] bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold">
            <Bot className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
            Ask GSH
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800/50 uppercase font-bold">
              AGENT
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden text-xs font-medium">
              <button
                onClick={() => setMode('text')}
                className={`px-3 py-1.5 flex items-center gap-1.5 transition-colors ${
                  mode === 'text'
                    ? 'bg-cyan-600 text-white'
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Text
              </button>
              <button
                onClick={() => {
                  setMode('voice');
                  if (!lkSession) startVoice();
                }}
                className={`px-3 py-1.5 flex items-center gap-1.5 transition-colors ${
                  mode === 'voice'
                    ? 'bg-cyan-600 text-white'
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <Mic className="w-3.5 h-3.5" />
                Voice
              </button>
            </div>
            <button
              onClick={handleClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          {mode === 'voice' && (
            <div className="flex-1 flex flex-col min-h-0">
              {lkError && (
                <div className="m-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-600 dark:text-rose-400">
                  {lkError}
                </div>
              )}
              {lkConnecting && !lkSession && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-500 dark:text-slate-400">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                  <p className="text-sm">Connecting to voice session…</p>
                </div>
              )}
              {lkSession && (
                <LiveKitRoom
                  token={lkSession.token}
                  serverUrl={lkSession.url}
                  connect
                  audio
                  className="flex-1 flex flex-col min-h-0"
                >
                  <RoomAudioRenderer />
                  <VoiceTab onDisconnect={stopVoice} />
                </LiveKitRoom>
              )}
              {!lkSession && !lkConnecting && !lkError && (
                <div className="flex-1 flex flex-col items-center justify-center gap-4">
                  <button
                    onClick={startVoice}
                    className="flex items-center gap-2 px-6 py-3 rounded-full bg-cyan-600 hover:bg-cyan-700 text-white font-semibold shadow-lg transition-colors"
                  >
                    <Mic className="w-5 h-5" />
                    Start voice session
                  </button>
                </div>
              )}
            </div>
          )}

          {mode === 'text' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {!response && !error && !isLoading && (
                <div className="space-y-2">
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">
                    Try asking:
                  </p>
                  {[
                    'What is the average latency right now?',
                    'Which servers are currently offline?',
                    'Show me the best performing server.',
                    'Show me recent incident events.',
                  ].map((hint) => (
                    <button
                      key={hint}
                      onClick={() => setQuestion(hint)}
                      className="w-full text-left text-xs px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:border-cyan-400 dark:hover:border-cyan-600 hover:text-cyan-700 dark:hover:text-cyan-300 transition-colors"
                    >
                      {hint}
                    </button>
                  ))}
                </div>
              )}

              {isLoading && (
                <div className="flex flex-col items-center justify-center py-12 text-slate-500 dark:text-slate-400 gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                  <p className="text-sm">Agent is thinking…</p>
                </div>
              )}

              {error && !isLoading && (
                <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800">
                  <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-rose-700 dark:text-rose-400">Something went wrong</p>
                    <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">{error}</p>
                  </div>
                </div>
              )}

              {response && !isLoading && (
                <div className="space-y-3">
                  {response.tool_used && (
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 font-mono">
                      <Wrench className="w-3.5 h-3.5 text-cyan-500" />
                      <span>
                        Tool:{' '}
                        <span className="text-cyan-600 dark:text-cyan-400 font-semibold">{response.tool_used}</span>
                      </span>
                    </div>
                  )}
                  <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <p className="text-[15px] text-slate-800 dark:text-slate-200 leading-7 whitespace-pre-wrap">
                      {response.answer}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setResponse(null);
                      setError(null);
                      setQuestion('');
                    }}
                    className="text-xs text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 transition-colors"
                  >
                    Ask another question
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {mode === 'text' && (
          <form
            onSubmit={handleSubmit}
            className="shrink-0 p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950"
          >
            <div className="flex flex-col gap-2">
              <textarea
                ref={textareaRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about server health, latency, events…"
                rows={1}
                disabled={isLoading}
                className="w-full resize-none overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm px-3 py-2.5 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-400 dark:focus:border-cyan-600 disabled:opacity-50 transition-colors"
              />
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-400 font-mono">Ctrl+Enter to send</span>
                <button
                  type="submit"
                  disabled={isLoading || !question.trim()}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-300 dark:disabled:bg-slate-700 text-white disabled:text-slate-500 text-xs font-semibold transition-colors"
                >
                  {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Send
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </>,
    document.body
  );
}