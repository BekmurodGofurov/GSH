import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Bot,
  Send,
  Loader2,
  Wrench,
  AlertTriangle,
  Mic,
  MicOff,
  MessageSquare,
  RotateCcw,
  AlertCircle,
  Clock,
  Sparkles,
} from 'lucide-react';
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

const SUGGESTED_QUERIES = [
  'What is the average latency right now?',
  'Which servers are currently offline?',
  'Show me the best performing server.',
  'Show me recent incident events.',
];

function formatEventTime(timeStr) {
  if (!timeStr) return '';
  try {
    const d = new Date(timeStr);
    if (isNaN(d.getTime())) return timeStr;
    const hours = String(d.getUTCHours()).padStart(2, '0');
    const mins = String(d.getUTCMinutes()).padStart(2, '0');
    const secs = String(d.getUTCSeconds()).padStart(2, '0');
    return `${hours}:${mins}:${secs} UTC`;
  } catch {
    return timeStr;
  }
}

function getEventTypeBadge(type) {
  const t = (type || '').toUpperCase();
  if (t.includes('CRASH') || t.includes('DOWN') || t.includes('OFFLINE')) {
    return {
      className: 'bg-rose-950/80 text-rose-300 border-rose-800/80',
      label: type,
    };
  }
  if (t.includes('PING') || t.includes('LATENCY')) {
    return {
      className: 'bg-amber-950/80 text-amber-300 border-amber-800/80',
      label: type,
    };
  }
  if (t.includes('RECOVERY') || t.includes('ONLINE')) {
    return {
      className: 'bg-emerald-950/80 text-emerald-300 border-emerald-800/80',
      label: type,
    };
  }
  return {
    className: 'bg-cyan-950/80 text-cyan-300 border-cyan-800/80',
    label: type,
  };
}

function getRootCauseBadge(cause) {
  const c = (cause || '').toUpperCase();
  if (c.includes('REGIONAL') || c.includes('OUTAGE')) {
    return 'bg-purple-950/80 text-purple-300 border-purple-800/80';
  }
  if (c.includes('DDOS') || c.includes('ATTACK')) {
    return 'bg-rose-950/80 text-rose-300 border-rose-800/80';
  }
  if (c.includes('PLAYER') || c.includes('DROP')) {
    return 'bg-blue-950/80 text-blue-300 border-blue-800/80';
  }
  if (c.includes('MAINTENANCE')) {
    return 'bg-sky-950/80 text-sky-300 border-sky-800/80';
  }
  return 'bg-slate-800 text-slate-300 border-slate-700/80';
}

function EventCard({ event }) {
  const typeBadge = getEventTypeBadge(event.eventType);
  const causeClass = getRootCauseBadge(event.rootCause);
  const timeFormatted = formatEventTime(event.time);

  return (
    <div className="rounded-xl border border-slate-800/90 bg-slate-900/90 p-3 space-y-2 hover:border-slate-700 transition-colors shadow-sm">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-cyan-400 text-xs">#{event.id}</span>
          {event.serverId && (
            <span className="font-mono text-[11px] text-slate-300 bg-slate-800 px-2 py-0.5 rounded border border-slate-700/60">
              {event.serverId}
            </span>
          )}
        </div>
        {event.eventType && (
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase border ${typeBadge.className}`}>
            {typeBadge.label}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 flex-wrap">
        {event.rootCause && (
          <span className={`px-1.5 py-0.5 rounded border font-sans font-medium ${causeClass}`}>
            {event.rootCause}
          </span>
        )}
        {timeFormatted && (
          <span className="flex items-center gap-1 text-slate-400">
            <Clock className="w-3 h-3 text-slate-500" />
            {timeFormatted}
          </span>
        )}
      </div>

      {event.message && (
        <p className="text-xs text-slate-300 leading-relaxed font-sans border-t border-slate-800/60 pt-1.5 mt-1">
          {event.message}
        </p>
      )}
    </div>
  );
}

function renderInline(text) {
  if (!text) return null;
  const parts = [];
  const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
  let lastIndex = 0;
  let match;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }
    const raw = match[0];
    if (raw.startsWith('**') && raw.endsWith('**')) {
      parts.push(
        <strong key={key++} className="font-semibold text-slate-100">
          {raw.slice(2, -2)}
        </strong>
      );
    } else if (raw.startsWith('`') && raw.endsWith('`')) {
      parts.push(
        <code
          key={key++}
          className="px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 font-mono text-[11px] border border-slate-700/60"
        >
          {raw.slice(1, -1)}
        </code>
      );
    } else if (raw.startsWith('*') && raw.endsWith('*')) {
      parts.push(
        <em key={key++} className="italic text-slate-200">
          {raw.slice(1, -1)}
        </em>
      );
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }
  return parts;
}

function parseMarkdownBlocks(text) {
  if (!text) return [];
  const lines = text.split('\n');
  const blocks = [];
  let currentList = null;
  let currentTable = null;
  let inCodeBlock = false;
  let codeLang = '';
  let codeLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        blocks.push({
          type: 'code',
          lang: codeLang,
          content: codeLines.join('\n'),
        });
        inCodeBlock = false;
        codeLines = [];
        codeLang = '';
      } else {
        if (currentList) {
          blocks.push(currentList);
          currentList = null;
        }
        if (currentTable) {
          blocks.push(currentTable);
          currentTable = null;
        }
        inCodeBlock = true;
        codeLang = line.trim().slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    const trimmed = line.trim();

    // Table detection
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (!currentTable) {
        if (currentList) {
          blocks.push(currentList);
          currentList = null;
        }
        currentTable = { type: 'table', rows: [] };
      }
      const isSep = trimmed.split('|').slice(1, -1).every((c) => c.trim().match(/^-+$/));
      if (!isSep) {
        const cells = trimmed.split('|').slice(1, -1).map((c) => c.trim());
        currentTable.rows.push(cells);
      }
      continue;
    } else if (currentTable) {
      blocks.push(currentTable);
      currentTable = null;
    }

    if (!trimmed) {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      continue;
    }

    if (trimmed.startsWith('### ')) {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      blocks.push({ type: 'h3', content: trimmed.slice(4) });
      continue;
    }
    if (trimmed.startsWith('## ')) {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      blocks.push({ type: 'h2', content: trimmed.slice(3) });
      continue;
    }
    if (trimmed.startsWith('# ')) {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      blocks.push({ type: 'h1', content: trimmed.slice(2) });
      continue;
    }

    const bulletMatch = line.match(/^(\s*)[*•-]\s+(.*)$/);
    if (bulletMatch) {
      const indent = bulletMatch[1].length;
      const content = bulletMatch[2];
      if (!currentList || currentList.type !== 'ul') {
        if (currentList) blocks.push(currentList);
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push({ indent, content });
      continue;
    }

    const numMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (numMatch) {
      const indent = numMatch[1].length;
      const content = numMatch[2];
      if (!currentList || currentList.type !== 'ol') {
        if (currentList) blocks.push(currentList);
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push({ indent, content });
      continue;
    }

    if (currentList) {
      blocks.push(currentList);
      currentList = null;
    }
    blocks.push({ type: 'p', content: line });
  }

  if (inCodeBlock) {
    blocks.push({ type: 'code', lang: codeLang, content: codeLines.join('\n') });
  }
  if (currentList) {
    blocks.push(currentList);
  }
  if (currentTable) {
    blocks.push(currentTable);
  }

  return blocks;
}

function parseEventMarkdown(content) {
  if (!content || !content.includes('**Event ID:**')) return null;
  const firstEventIndex = content.search(/[*•-]?\s*\*\*Event ID:\*\*/);
  if (firstEventIndex < 0) return null;
  const prefix = content.slice(0, firstEventIndex).trim();

  const eventRegex = /[*•-]?\s*\*\*Event ID:\*\*\s*(\d+)[\s\S]*?(?=(?:[*•-]?\s*\*\*Event ID:\*\*|\n\n[^\s*•-]|$))/g;
  const events = [];
  let match;
  let lastIndex = firstEventIndex;
  while ((match = eventRegex.exec(content)) !== null) {
    const block = match[0];
    const id = match[1];
    const timeMatch = block.match(/\*\*Time:\*\*\s*([^\n]+)/);
    const serverMatch = block.match(/\*\*Server ID:\*\*\s*([^\n]+)/);
    const typeMatch = block.match(/\*\*Event Type:\*\*\s*([^\n]+)/);
    const causeMatch = block.match(/\*\*Root Cause:\*\*\s*([^\n]+)/);
    const msgMatch = block.match(/\*\*Message:\*\*\s*([^\n]+)/);
    events.push({
      id,
      time: timeMatch ? timeMatch[1].trim() : '',
      serverId: serverMatch ? serverMatch[1].trim() : '',
      eventType: typeMatch ? typeMatch[1].trim() : '',
      rootCause: causeMatch ? causeMatch[1].trim() : '',
      message: msgMatch ? msgMatch[1].trim() : '',
    });
    lastIndex = eventRegex.lastIndex;
  }
  const suffix = content.slice(lastIndex).trim();
  return { prefix, events, suffix };
}

function GeneralMarkdown({ content }) {
  const blocks = parseMarkdownBlocks(content);
  return (
    <div className="space-y-2 text-xs leading-relaxed text-slate-200">
      {blocks.map((block, idx) => {
        if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
          return (
            <h4 key={idx} className="text-xs font-bold text-cyan-300 mt-2 mb-1 tracking-wide uppercase">
              {renderInline(block.content)}
            </h4>
          );
        }
        if (block.type === 'ul') {
          return (
            <ul key={idx} className="space-y-1.5 my-1.5">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx} className={`flex items-start gap-2 ${item.indent > 0 ? 'ml-3' : ''}`}>
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                  <span className="leading-relaxed">{renderInline(item.content)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={idx} className="space-y-1.5 my-1.5 list-decimal list-inside text-slate-200">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx} className="leading-relaxed">
                  {renderInline(item.content)}
                </li>
              ))}
            </ol>
          );
        }
        if (block.type === 'code') {
          return (
            <pre key={idx} className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-cyan-300 overflow-x-auto my-2">
              <code>{block.content}</code>
            </pre>
          );
        }
        if (block.type === 'table') {
          return (
            <div key={idx} className="overflow-x-auto my-2 rounded-xl border border-slate-800 bg-slate-900/60">
              <table className="w-full text-[11px] text-left">
                <tbody>
                  {block.rows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className={
                        rIdx === 0
                          ? 'bg-slate-800/80 font-semibold text-cyan-300 border-b border-slate-700/60'
                          : 'border-b border-slate-800/40 last:border-none'
                      }
                    >
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-1.5">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return (
          <p key={idx} className="leading-relaxed">
            {renderInline(block.content)}
          </p>
        );
      })}
    </div>
  );
}

function MarkdownContent({ content }) {
  if (!content) return null;
  const eventData = parseEventMarkdown(content);
  if (eventData && eventData.events.length > 0) {
    return (
      <div className="space-y-2.5">
        {eventData.prefix && <GeneralMarkdown content={eventData.prefix} />}
        <div className="flex items-center justify-between text-[11px] font-mono text-cyan-400 mt-2 mb-1.5 px-0.5">
          <span className="flex items-center gap-1.5 font-bold">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            Recent Incidents ({eventData.events.length})
          </span>
        </div>
        <div className="space-y-2">
          {eventData.events.map((ev) => (
            <EventCard key={ev.id} event={ev} />
          ))}
        </div>
        {eventData.suffix && <GeneralMarkdown content={eventData.suffix} />}
      </div>
    );
  }
  return <GeneralMarkdown content={content} />;
}

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
function VoiceTab({ onDisconnect, onError }) {
  const { state, audioTrack, error: agentError } = useVoiceAssistant();
  const connectionState = useConnectionState();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const room = useRoomContext();
  const transcriptEndRef = useRef(null);
  const inactivityTimerRef = useRef(null);

  useEffect(() => {
    if (agentError) {
      onError?.(`Voice agent error: ${agentError?.message || agentError}. Gemini quota or live connection may be unavailable.`);
    }
  }, [agentError, onError]);

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

// ─── Text Chat Tab ───────────────────────────────────────────────────────────
function TextTab({ messages, isLoading, error, onSendQuery, onClearMessages }) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  const resizeInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const needed = el.scrollHeight;
    el.style.height = `${Math.min(needed, MAX_INPUT_HEIGHT)}px`;
    el.style.overflowY = needed > MAX_INPUT_HEIGHT ? 'auto' : 'hidden';
  }, []);

  useEffect(resizeInput, [input, resizeInput]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input;
    setInput('');
    onSendQuery(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#080e1a]">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto mx-4 my-3 rounded-2xl border border-slate-800/60 bg-slate-900/40 p-3.5 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 py-8 text-center">
            <div className="w-12 h-12 rounded-2xl bg-cyan-950/60 border border-cyan-800/40 flex items-center justify-center shadow-lg shadow-cyan-950/50">
              <Bot className="w-6 h-6 text-cyan-400" />
            </div>
            <div className="max-w-[320px]">
              <h3 className="text-sm font-semibold text-slate-100 mb-1">GSH AI Assistant</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ask about server health, average latency, online status, or recent anomaly events.
              </p>
            </div>
            <div className="w-full max-w-[440px] space-y-2 pt-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-bold text-left px-1">
                Try asking:
              </p>
              {SUGGESTED_QUERIES.map((hint) => (
                <button
                  key={hint}
                  type="button"
                  onClick={() => onSendQuery(hint)}
                  className="w-full text-left text-xs px-3.5 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800/90 text-slate-300 hover:border-cyan-500/60 hover:text-cyan-200 hover:bg-slate-800/80 transition-all flex items-center justify-between group cursor-pointer shadow-sm"
                >
                  <span>{hint}</span>
                  <span className="text-[10px] font-mono text-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                    Send <Send className="w-3 h-3" />
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => {
              const isUser = msg.role === 'user';
              if (isUser) {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-[85%] px-3.5 py-2.5 text-xs leading-relaxed bg-slate-800/90 text-slate-100 border border-slate-700/60 rounded-2xl rounded-br-sm shadow-sm">
                      <span className="block text-[10px] font-bold text-slate-400 mb-1">You</span>
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                    </div>
                  </div>
                );
              }
              return (
                <div key={msg.id} className="flex justify-start">
                  <div
                    className={`max-w-[92%] px-4 py-3 text-xs leading-relaxed rounded-2xl rounded-bl-sm shadow-md border ${
                      msg.isError
                        ? 'bg-rose-950/40 text-rose-200 border-rose-800/60'
                        : 'bg-gradient-to-br from-cyan-950/40 via-slate-900/90 to-slate-950 text-slate-200 border-cyan-800/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-cyan-900/30">
                      <div className="flex items-center gap-1.5">
                        <Bot className={`w-3.5 h-3.5 ${msg.isError ? 'text-rose-400' : 'text-cyan-400'}`} />
                        <span className={`text-[10px] font-bold tracking-wider uppercase ${msg.isError ? 'text-rose-400' : 'text-cyan-400'}`}>
                          GSH Agent
                        </span>
                      </div>
                      {msg.tool_used && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950/90 text-cyan-300 border border-cyan-800/60">
                          <Wrench className="w-3 h-3 text-cyan-400" />
                          {msg.tool_used}
                        </span>
                      )}
                    </div>
                    {msg.isError ? (
                      <p className="text-rose-300 font-mono text-[11px]">{msg.text}</p>
                    ) : (
                      <MarkdownContent content={msg.text} />
                    )}
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className="flex justify-start">
                <div className="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-gradient-to-br from-cyan-950/30 via-slate-900/80 to-slate-950 border border-cyan-800/30 flex items-center gap-2.5 text-xs text-cyan-300 shadow-sm">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                  <span className="font-mono text-[11px]">Analyzing telemetry & generating answer…</span>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Chips when chat is active */}
      {messages.length > 0 && (
        <div className="shrink-0 flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none px-4 text-xs">
          {SUGGESTED_QUERIES.map((hint) => (
            <button
              key={hint}
              type="button"
              onClick={() => onSendQuery(hint)}
              disabled={isLoading}
              className="shrink-0 text-[11px] px-3 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-cyan-300 hover:border-cyan-800/60 transition-colors cursor-pointer disabled:opacity-50"
            >
              {hint}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="shrink-0 p-3 sm:p-4 border-t border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="flex flex-col gap-2">
          <div className="relative flex items-center">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about servers, latency, recent incidents… (Enter to send)"
              rows={1}
              disabled={isLoading}
              className="w-full resize-none rounded-xl border border-slate-800 bg-slate-900/90 text-slate-100 text-xs sm:text-sm px-3.5 py-2.5 pr-20 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/60 focus:border-cyan-500/80 disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2 bottom-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 active:scale-95 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-cyan-950/50 transition-all cursor-pointer"
            >
              {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>Send</span>
            </button>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono px-1">
            <span>Enter to send • Shift+Enter for new line</span>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={onClearMessages}
                className="flex items-center gap-1 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                Clear chat
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

// ─── Main Panel Container ────────────────────────────────────────────────────
export function AskPanel({ isOpen, onOpen, onClose }) {
  const [mode, setMode] = useState('text');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
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

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, handleClose]);

  const handleSendQuery = async (queryText) => {
    const q = queryText?.trim();
    if (!q || isLoading) return;
    setError(null);
    const userMsg = {
      id: `u_${Date.now()}`,
      role: 'user',
      text: q,
      time: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const { data, error: err } = await api.askAgent(q);
    setIsLoading(false);
    if (err) {
      setError(err);
      const errorMsg = {
        id: `err_${Date.now()}`,
        role: 'agent',
        text: `Error: ${err}`,
        isError: true,
        time: Date.now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } else if (data) {
      const agentMsg = {
        id: `a_${Date.now()}`,
        role: 'agent',
        text: data.answer,
        tool_used: data.tool_used,
        time: Date.now(),
      };
      setMessages((prev) => [...prev, agentMsg]);
    }
  };

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
        className={`fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-[2px] transition-opacity duration-300 ease-in-out ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />

      <div
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[560px] lg:w-[680px] xl:w-[760px] bg-[#080e1a] border-l border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col text-slate-100 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-2 text-slate-100 font-bold">
            <Bot className="w-5 h-5 text-cyan-400" />
            Ask GSH
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/50 uppercase font-bold">
              AGENT
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-slate-800 bg-slate-900/80 p-0.5 text-xs font-medium">
              <button
                type="button"
                onClick={() => setMode('text')}
                className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors cursor-pointer ${
                  mode === 'text'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Text
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('voice');
                  if (!lkSession) startVoice();
                }}
                className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors cursor-pointer ${
                  mode === 'voice'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Mic className="w-3.5 h-3.5" />
                Voice
              </button>
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="p-1.5 text-slate-400 hover:text-slate-200 rounded-md hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          {mode === 'voice' ? (
            <div className="flex-1 flex flex-col min-h-0">
              {lkError && (
                <div className="m-4 p-3 rounded-xl bg-rose-950/40 border border-rose-800 text-xs text-rose-300">
                  {lkError}
                </div>
              )}
              {lkConnecting && !lkSession && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
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
                  onDisconnected={() => {
                    setLkError('Voice session disconnected. You can start a new session below.');
                    stopVoice();
                  }}
                  onError={(err) => {
                    setLkError(`Voice connection error: ${err?.message || err}. Please try reconnecting.`);
                    stopVoice();
                  }}
                >
                  <RoomAudioRenderer />
                  <VoiceTab onDisconnect={stopVoice} onError={(msg) => setLkError(msg)} />
                </LiveKitRoom>
              )}
              {!lkSession && !lkConnecting && !lkError && (
                <div className="flex-1 flex flex-col items-center justify-center gap-4">
                  <button
                    type="button"
                    onClick={startVoice}
                    className="flex items-center gap-2 px-6 py-3 rounded-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold shadow-lg shadow-cyan-950/50 transition-colors cursor-pointer"
                  >
                    <Mic className="w-5 h-5" />
                    Start voice session
                  </button>
                </div>
              )}
            </div>
          ) : (
            <TextTab
              messages={messages}
              isLoading={isLoading}
              error={error}
              onSendQuery={handleSendQuery}
              onClearMessages={() => setMessages([])}
            />
          )}
        </div>
      </div>
    </>,
    document.body
  );
}