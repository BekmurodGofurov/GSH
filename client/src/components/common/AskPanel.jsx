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
  RotateCcw,
  AlertCircle,
  Clock,
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
import { ConnectionState } from 'livekit-client';

const MAX_INPUT_HEIGHT = 180;
const INACTIVITY_TIMEOUT_S = 60;

const SUGGESTED_QUERIES = [
  'How many players are online right now?',
  'Which server is performing best, and why?',
  'Which servers are currently offline?',
  'Show the 5 worst servers.',
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
      className:
        'bg-rose-100 text-rose-700 border-rose-300 dark:bg-rose-950/80 dark:text-rose-300 dark:border-rose-800/80',
      label: type,
    };
  }
  if (t.includes('PING') || t.includes('LATENCY')) {
    return {
      className:
        'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-950/80 dark:text-amber-300 dark:border-amber-800/80',
      label: type,
    };
  }
  if (t.includes('RECOVERY') || t.includes('ONLINE')) {
    return {
      className:
        'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-950/80 dark:text-emerald-300 dark:border-emerald-800/80',
      label: type,
    };
  }
  return {
    className:
      'bg-cyan-100 text-cyan-700 border-cyan-300 dark:bg-cyan-950/80 dark:text-cyan-300 dark:border-cyan-800/80',
    label: type,
  };
}

function getRootCauseBadge(cause) {
  const c = (cause || '').toUpperCase();
  if (c.includes('REGIONAL') || c.includes('OUTAGE')) {
    return 'bg-purple-100 text-purple-700 border-purple-300 dark:bg-purple-950/80 dark:text-purple-300 dark:border-purple-800/80';
  }
  if (c.includes('DDOS') || c.includes('ATTACK')) {
    return 'bg-rose-100 text-rose-700 border-rose-300 dark:bg-rose-950/80 dark:text-rose-300 dark:border-rose-800/80';
  }
  if (c.includes('PLAYER') || c.includes('DROP')) {
    return 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-950/80 dark:text-blue-300 dark:border-blue-800/80';
  }
  if (c.includes('MAINTENANCE')) {
    return 'bg-sky-100 text-sky-700 border-sky-300 dark:bg-sky-950/80 dark:text-sky-300 dark:border-sky-800/80';
  }
  return 'bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700/80';
}

function EventCard({ event }) {
  const typeBadge = getEventTypeBadge(event.eventType);
  const causeClass = getRootCauseBadge(event.rootCause);
  const timeFormatted = formatEventTime(event.time);

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-slate-900/90 p-3 space-y-2 hover:border-slate-300 dark:hover:border-slate-700 transition-colors shadow-sm">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-cyan-600 dark:text-cyan-400 text-xs">#{event.id}</span>
          {event.serverId && (
            <span className="font-mono text-[11px] text-slate-700 dark:text-slate-300 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-300 dark:border-slate-700/60">
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

      <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500 dark:text-slate-400 flex-wrap">
        {event.rootCause && (
          <span className={`px-1.5 py-0.5 rounded border font-sans font-medium ${causeClass}`}>
            {event.rootCause}
          </span>
        )}
        {timeFormatted && (
          <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
            <Clock className="w-3 h-3 text-slate-500 dark:text-slate-500" />
            {timeFormatted}
          </span>
        )}
      </div>

      {event.message && (
        <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-sans border-t border-slate-200 dark:border-slate-800/60 pt-1.5 mt-1">
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
        <strong key={key++} className="font-semibold text-slate-900 dark:text-slate-100">
          {raw.slice(2, -2)}
        </strong>
      );
    } else if (raw.startsWith('`') && raw.endsWith('`')) {
      parts.push(
        <code
          key={key++}
          className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-cyan-700 dark:text-cyan-300 font-mono text-[11px] border border-slate-300 dark:border-slate-700/60"
        >
          {raw.slice(1, -1)}
        </code>
      );
    } else if (raw.startsWith('*') && raw.endsWith('*')) {
      parts.push(
        <em key={key++} className="italic text-slate-800 dark:text-slate-200">
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
    <div className="space-y-2 text-xs leading-relaxed text-slate-800 dark:text-slate-200">
      {blocks.map((block, idx) => {
        if (block.type === 'h1' || block.type === 'h2' || block.type === 'h3') {
          return (
            <h4 key={idx} className="text-xs font-bold text-cyan-700 dark:text-cyan-300 mt-2 mb-1 tracking-wide uppercase">
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
            <ol key={idx} className="space-y-1.5 my-1.5 list-decimal list-inside text-slate-800 dark:text-slate-200">
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
            <pre key={idx} className="p-3 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-cyan-700 dark:text-cyan-300 overflow-x-auto my-2">
              <code>{block.content}</code>
            </pre>
          );
        }
        if (block.type === 'table') {
          return (
            <div key={idx} className="overflow-x-auto my-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60">
              <table className="w-full text-[11px] text-left">
                <tbody>
                  {block.rows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className={
                        rIdx === 0
                          ? 'bg-slate-100 dark:bg-slate-800/80 font-semibold text-cyan-700 dark:text-cyan-300 border-b border-slate-300 dark:border-slate-700/60'
                          : 'border-b border-slate-200 dark:border-slate-800/40 last:border-none'
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
        <div className="flex items-center justify-between text-[11px] font-mono text-cyan-600 dark:text-cyan-400 mt-2 mb-1.5 px-0.5">
          <span className="flex items-center gap-1.5 font-bold">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
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
//
// The first row is the one the question was about -- the best server, or
// the worst when the user asked for the worst -- so it is drawn apart:
// a gradient bar, a glow, a label and a medal, where the rest are plain.
// Colours come from CSS classes (not inline hex) so the chart follows the
// panel between light and dark.
// Long game-server titles would run off the left edge of the chart.
function shortLabel(label, max = 26) {
  const text = String(label ?? '');
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function BarChart({ title, rows, unit = 'ms', order = 'best' }) {
  if (!rows || rows.length === 0) return null;
  const isWorst = order === 'worst';
  const max = Math.max(...rows.map((r) => r.value || 0), 1);
  const BAR_H = 20;
  const GAP = 8;
  const LABEL_W = 170;
  const BAR_MAX_W = 130;
  const VALUE_W = 110;
  const width = LABEL_W + BAR_MAX_W + VALUE_W;
  const svgH = rows.length * (BAR_H + GAP) + 4;

  const accent = isWorst ? 'rose' : 'emerald';

  return (
    <div
      className={`my-2 rounded-xl border bg-white dark:bg-slate-900/90 px-3 pt-3 pb-2 shadow-sm ${
        isWorst
          ? 'border-rose-300 dark:border-rose-800/50'
          : 'border-cyan-200 dark:border-cyan-800/40'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-[10px] font-bold text-cyan-700 dark:text-cyan-400 uppercase tracking-wider">
          {title}
        </p>
        <span
          className={`shrink-0 text-[9px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${
            isWorst
              ? 'bg-rose-100 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60'
              : 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800/60'
          }`}
        >
          {rows.length} {rows.length === 1 ? 'server' : 'servers'}
        </span>
      </div>
      {/* viewBox + width:100% so the chart shrinks to fit a phone-width
          panel instead of pushing a horizontal scrollbar into the chat. */}
      <svg
        viewBox={`0 0 ${width} ${svgH}`}
        width="100%"
        height={svgH}
        preserveAspectRatio="xMinYMin meet"
        role="img"
        aria-label={title}
      >
        <defs>
          <linearGradient id="gsh-bar-best" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#facc15" />
          </linearGradient>
          <linearGradient id="gsh-bar-worst" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#f43f5e" />
            <stop offset="100%" stopColor="#fb923c" />
          </linearGradient>
        </defs>
        {rows.map((row, i) => {
          const y = i * (BAR_H + GAP);
          const barW = max > 0 ? Math.round((row.value / max) * BAR_MAX_W) : 4;
          const w = Math.max(barW, 4);
          const star = Boolean(row.highlight);
          return (
            <g key={i}>
              <text
                x={LABEL_W - 6}
                y={y + BAR_H / 2 + 4}
                textAnchor="end"
                fontSize="9"
                fontFamily="monospace"
                fontWeight={star ? 700 : 400}
                className={
                  star
                    ? accent === 'rose'
                      ? 'fill-rose-700 dark:fill-rose-300'
                      : 'fill-emerald-700 dark:fill-emerald-300'
                    : 'fill-slate-500 dark:fill-slate-400'
                }
              >
                {star ? '★ ' : ''}
                {shortLabel(row.label)}
              </text>
              {star ? (
                <rect
                  x={LABEL_W}
                  y={y + 1}
                  width={w}
                  height={BAR_H - 2}
                  rx={4}
                  fill={`url(#gsh-bar-${isWorst ? 'worst' : 'best'})`}
                  className={isWorst ? 'drop-shadow-[0_0_6px_rgba(244,63,94,0.55)]' : 'drop-shadow-[0_0_6px_rgba(16,185,129,0.55)]'}
                />
              ) : (
                <rect
                  x={LABEL_W}
                  y={y + 3}
                  width={w}
                  height={BAR_H - 6}
                  rx={3}
                  className="fill-cyan-500/70 dark:fill-cyan-400/70"
                />
              )}
              <text
                x={LABEL_W + w + 5}
                y={y + BAR_H / 2 + 4}
                fontSize="9"
                fontFamily="monospace"
                fontWeight={star ? 700 : 400}
                className="fill-slate-800 dark:fill-slate-200"
              >
                {row.value}
                {unit}
                {/* The bar is latency, but the ranking turns on stability
                    too -- so the crash count rides along with the bar
                    rather than living only in the spoken answer. */}
                {row.note && (
                  <tspan className="fill-amber-600 dark:fill-amber-400" dx="6">
                    {row.note}
                  </tspan>
                )}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Message bubbles ─────────────────────────────────────────────────────────

function UserBubble({ item }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] px-3.5 py-2.5 text-xs leading-relaxed bg-cyan-600 text-white border border-cyan-700 dark:bg-slate-800/90 dark:text-slate-100 dark:border-slate-700/60 rounded-2xl rounded-br-sm shadow-sm">
        <span className="flex items-center gap-1 text-[10px] font-bold text-cyan-100 dark:text-slate-400 mb-1">
          You
          {item.viaVoice && <Mic className="w-2.5 h-2.5 text-cyan-200 dark:text-slate-500" />}
          {!item.final && item.viaVoice && (
            <span className="font-normal italic opacity-70">speaking…</span>
          )}
        </span>
        <p className="whitespace-pre-wrap">{item.text}</p>
      </div>
    </div>
  );
}

function AgentBubble({ item }) {
  // A spoken reply arrives a word at a time and is plain speech, so it
  // renders as a light bubble. A typed reply arrives complete and may
  // carry markdown, incident cards or a tool badge.
  if (item.viaVoice) {
    return (
      <div className="flex justify-start">
        <div
          className={`max-w-[85%] px-3.5 py-2 text-xs leading-relaxed bg-gradient-to-br from-cyan-100 dark:from-cyan-900/50 to-white dark:to-slate-900/60 text-cyan-900 dark:text-cyan-100 border border-cyan-200 dark:border-cyan-800/30 rounded-2xl rounded-bl-sm ${
            item.final ? 'opacity-100' : 'opacity-80'
          }`}
        >
          <span className="flex items-center gap-1 text-[10px] font-bold text-cyan-600 dark:text-cyan-500 mb-0.5">
            GSH
            <Mic className="w-2.5 h-2.5" />
            {!item.final && <span className="font-normal italic opacity-70">speaking…</span>}
          </span>
          {item.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[92%] px-4 py-3 text-xs leading-relaxed rounded-2xl rounded-bl-sm shadow-md border ${
          item.isError
            ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200 border-rose-300 dark:border-rose-800/60'
            : 'bg-gradient-to-br from-cyan-50 dark:from-cyan-950/40 via-white dark:via-slate-900/90 to-slate-50 dark:to-slate-950 text-slate-800 dark:text-slate-200 border-cyan-200 dark:border-cyan-800/40'
        }`}
      >
        <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-cyan-100 dark:border-cyan-900/30">
          <div className="flex items-center gap-1.5">
            <Bot className={`w-3.5 h-3.5 ${item.isError ? 'text-rose-600 dark:text-rose-400' : 'text-cyan-600 dark:text-cyan-400'}`} />
            <span
              className={`text-[10px] font-bold tracking-wider uppercase ${
                item.isError ? 'text-rose-600 dark:text-rose-400' : 'text-cyan-600 dark:text-cyan-400'
              }`}
            >
              GSH Agent
            </span>
          </div>
          {item.tool_used && (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-100 dark:bg-cyan-950/90 text-cyan-700 dark:text-cyan-300 border border-cyan-300 dark:border-cyan-800/60">
              <Wrench className="w-3 h-3 text-cyan-600 dark:text-cyan-400" />
              {item.tool_used}
            </span>
          )}
        </div>
        {item.isError ? (
          <p className="text-rose-700 dark:text-rose-300 font-mono text-[11px]">{item.text}</p>
        ) : (
          <MarkdownContent content={item.text} />
        )}
      </div>
    </div>
  );
}

function ConversationItem({ item }) {
  if (item.role === 'chart') {
    return (
      <BarChart
        title={item.chart.title}
        rows={item.chart.rows}
        unit={item.chart.unit}
        order={item.chart.order}
      />
    );
  }
  if (item.role === 'user') return <UserBubble item={item} />;
  return <AgentBubble item={item} />;
}

// ─── Voice plumbing (must render inside LiveKitRoom) ─────────────────────────

/**
 * Feeds the live room's charts and transcripts into the one shared
 * conversation. It renders nothing: the bubbles are drawn by the same
 * list that holds the typed messages, so a spoken answer and a typed one
 * sit in a single thread.
 */
function VoiceStreamBridge({ onChart, onTranscript, onFinalise, onError }) {
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const { error: agentError } = useVoiceAssistant();

  useEffect(() => {
    if (agentError) {
      onError?.(
        `Voice agent error: ${agentError?.message || agentError}. The live model may be unavailable or out of quota.`
      );
    }
  }, [agentError, onError]);

  useDataChannel((msg) => {
    try {
      const data = JSON.parse(new TextDecoder().decode(msg.payload));
      if (data.type === 'chart') onChart(data);
    } catch {
      // not a json payload
    }
  });

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
          // Drop filler the recogniser emits between words (".", "…").
          if (!/[a-zA-Z0-9]/.test(cleanText)) continue;
          onTranscript(streamId, role, cleanText);
        }
      } catch {
        // Stream aborted or closed
      }

      onFinalise(streamId, accumulated.trim());
    };

    try {
      room.registerTextStreamHandler('lk.transcription', handleTextStream);
    } catch {
      // Handler already registered
    }

    return () => {
      try {
        room.unregisterTextStreamHandler('lk.transcription');
      } catch {
        // Already gone with the room
      }
    };
  }, [room, localParticipant, onTranscript, onFinalise]);

  return null;
}

/**
 * The mic control and level meter, shown in the composer while a voice
 * session is live.
 */
function LiveVoiceControls({ onIdleTimeout, lastActivityAt }) {
  const { state, audioTrack } = useVoiceAssistant();
  const connectionState = useConnectionState();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const idleTimerRef = useRef(null);

  const toggleMic = useCallback(async () => {
    if (localParticipant) {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
    }
  }, [localParticipant, isMicrophoneEnabled]);

  // Hang up only after a real lull.
  //
  // 'thinking' used to count as idle, so a question that needed a slow
  // tool call could have the session closed out from under it mid-answer
  // -- and the reconnect that followed started a fresh agent session.
  // Typing counts as activity too: lastActivityAt re-arms the timer.
  useEffect(() => {
    const busy = state === 'listening' || state === 'thinking' || state === 'speaking';
    clearTimeout(idleTimerRef.current);
    if (!busy) {
      idleTimerRef.current = setTimeout(onIdleTimeout, INACTIVITY_TIMEOUT_S * 1000);
    }
    return () => clearTimeout(idleTimerRef.current);
  }, [state, lastActivityAt, onIdleTimeout]);

  const isConnected = connectionState === ConnectionState.Connected;
  const isMuted = !isMicrophoneEnabled;

  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        onClick={toggleMic}
        disabled={!isConnected}
        title={isMuted ? 'Microphone is muted — click to unmute' : 'Microphone is active — click to mute'}
        aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
        className={`relative flex items-center justify-center w-10 h-10 shrink-0 rounded-full border-2 transition-all duration-200 active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-wait ${
          isMuted
            ? 'bg-white dark:bg-slate-900 border-rose-500 text-rose-600 dark:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            : state === 'speaking'
              ? 'bg-violet-600 border-violet-400 text-white shadow-[0_0_18px_rgba(139,92,246,0.45)]'
              : 'bg-cyan-600 border-cyan-400 text-white shadow-[0_0_18px_rgba(6,182,212,0.45)]'
        }`}
      >
        {!isMuted && state === 'listening' && (
          <span
            className="absolute inset-0 rounded-full bg-cyan-500/30 animate-ping"
            style={{ animationDuration: '1.4s' }}
          />
        )}
        {isMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
      </button>

      <div className="flex-1 min-w-0">
        <BarVisualizer state={state} trackRef={audioTrack} className="w-full h-5" />
        <span className="block text-[10px] font-mono text-slate-500 dark:text-slate-500 truncate">
          {!isConnected
            ? 'Connecting…'
            : isMuted
              ? 'Mic muted — click to speak'
              : state === 'speaking'
                ? 'GSH speaking…'
                : state === 'thinking'
                  ? 'Checking the servers…'
                  : 'Listening — speak now'}
        </span>
      </div>

      <StartAudio
        label="Enable audio"
        type="button"
        className="shrink-0 px-2.5 py-1 bg-cyan-600/80 hover:bg-cyan-600 text-white rounded-full text-[10px] font-semibold transition-colors"
      />
    </div>
  );
}

// ─── The one conversation: typed and spoken in a single thread ───────────────

function Conversation({
  items,
  isLoading,
  input,
  onInputChange,
  onSendQuery,
  onClearItems,
  voiceSlot,
}) {
  const textareaRef = useRef(null);
  const itemsEndRef = useRef(null);

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
    itemsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [items, isLoading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input;
    onInputChange('');
    onSendQuery(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-[#080e1a]">
      <div className="flex-1 overflow-y-auto mx-4 my-3 rounded-2xl border border-slate-200 dark:border-slate-800/60 bg-white/80 dark:bg-slate-900/40 p-3.5 space-y-3 min-h-0">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 py-8 text-center">
            <div className="w-12 h-12 rounded-2xl bg-cyan-100 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-800/40 flex items-center justify-center shadow-lg shadow-cyan-200/60 dark:shadow-cyan-950/50">
              <Bot className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            </div>
            <div className="max-w-[340px]">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">GSH AI Assistant</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Type a question or tap the microphone and talk. Ask about server health,
                latency, which server is performing best, or recent incidents.
              </p>
            </div>
            <div className="w-full max-w-[440px] space-y-2 pt-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-500 font-bold text-left px-1">
                Try asking:
              </p>
              {SUGGESTED_QUERIES.map((hint) => (
                <button
                  key={hint}
                  type="button"
                  onClick={() => onSendQuery(hint)}
                  className="w-full text-left text-xs px-3.5 py-2.5 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800/90 text-slate-700 dark:text-slate-300 hover:border-cyan-500 dark:hover:border-cyan-500/60 hover:text-cyan-700 dark:hover:text-cyan-200 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-all flex items-center justify-between group cursor-pointer shadow-sm"
                >
                  <span>{hint}</span>
                  <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                    Send <Send className="w-3 h-3" />
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {items.map((item) => (
              <ConversationItem key={item.id} item={item} />
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="px-4 py-2.5 rounded-2xl rounded-bl-sm bg-gradient-to-br from-cyan-50 dark:from-cyan-950/30 via-white dark:via-slate-900/80 to-slate-50 dark:to-slate-950 border border-cyan-200 dark:border-cyan-800/30 flex items-center gap-2.5 text-xs text-cyan-700 dark:text-cyan-300 shadow-sm">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-600 dark:text-cyan-400" />
                  <span className="font-mono text-[11px]">Analyzing telemetry & generating answer…</span>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={itemsEndRef} />
      </div>

      {items.length > 0 && (
        <div className="shrink-0 flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none px-4 text-xs">
          {SUGGESTED_QUERIES.map((hint) => (
            <button
              key={hint}
              type="button"
              onClick={() => onSendQuery(hint)}
              disabled={isLoading}
              className="shrink-0 text-[11px] px-3 py-1 rounded-full bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:text-cyan-700 dark:hover:text-cyan-300 hover:border-cyan-500 dark:hover:border-cyan-800/60 transition-colors cursor-pointer disabled:opacity-50"
            >
              {hint}
            </button>
          ))}
        </div>
      )}

      {/* The composer: a text box and a microphone, side by side, for the
          one conversation above. The mic controls sit outside the <form>
          on purpose -- LiveKit's own buttons (StartAudio) render without a
          `type`, which inside a form defaults to submit, so enabling audio
          would fire off whatever question was half-typed in the box. */}
      <div className="shrink-0 flex flex-col gap-2.5 p-3 sm:p-4 border-t border-slate-200 dark:border-slate-800/80 bg-white/90 dark:bg-slate-950/80 backdrop-blur-md">
        <form onSubmit={handleSubmit}>
          <div className="relative flex items-center">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about servers, latency, recent incidents… (Enter to send)"
              rows={1}
              disabled={isLoading}
              className="w-full resize-none rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 text-slate-900 dark:text-slate-100 text-xs sm:text-sm px-3.5 py-2.5 pr-20 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/60 focus:border-cyan-500/80 disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2 bottom-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 active:scale-95 disabled:bg-slate-200 dark:disabled:bg-slate-800 disabled:text-slate-400 dark:disabled:text-slate-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-cyan-200/60 dark:shadow-cyan-950/50 transition-all cursor-pointer"
            >
              {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>Send</span>
            </button>
          </div>
        </form>

        {voiceSlot}

        <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-500 font-mono px-1">
          <span>Enter to send • Shift+Enter for new line</span>
          {items.length > 0 && (
            <button
              type="button"
              onClick={onClearItems}
              className="flex items-center gap-1 text-slate-500 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              Clear chat
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Panel Container ────────────────────────────────────────────────────
export function AskPanel({ isOpen, onOpen, onClose }) {
  // One list for the whole conversation. Typed questions, spoken
  // questions, answers and charts all land here in the order they
  // happened -- there is no separate text tab and voice tab to switch
  // between, and nothing to lose when you change how you are asking.
  const [items, setItems] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lkSession, setLkSession] = useState(null);
  const [lkConnecting, setLkConnecting] = useState(false);
  const [lkError, setLkError] = useState(null);
  const [lastActivityAt, setLastActivityAt] = useState(Date.now());

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const startVoice = useCallback(async () => {
    setLkConnecting(true);
    setLkError(null);
    const { data, error: err } = await api.getLivekitToken();
    setLkConnecting(false);
    if (err || !data) {
      setLkError(err || 'Could not get voice session token.');
      return;
    }
    setLkSession({ token: data.token, url: data.url });
    setLastActivityAt(Date.now());
  }, []);

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

  // ── Voice → conversation ──────────────────────────────────────────────

  const addChart = useCallback((data) => {
    setItems((prev) => {
      // The worker may republish a chart; don't stack duplicates.
      const recent = prev.slice(-2).find((m) => m.role === 'chart' && m.chart?.title === data.title);
      if (recent) return prev;
      return [
        ...prev,
        {
          id: `chart_${Date.now()}`,
          role: 'chart',
          chart: { title: data.title, rows: data.rows, unit: data.unit || 'ms', order: data.order || 'best' },
          time: Date.now(),
        },
      ];
    });
  }, []);

  const upsertTranscript = useCallback((streamId, role, text) => {
    setItems((prev) => {
      const list = [...prev];
      const idx = list.findIndex((m) => m.id === streamId);
      if (idx >= 0) {
        list[idx] = { ...list[idx], text, final: false };
        return list;
      }

      // A continuation of the speaker's current turn extends that bubble
      // rather than starting another one.
      const last = list[list.length - 1];
      if (
        last &&
        last.viaVoice &&
        last.role === role &&
        (!last.final || (Date.now() - (last.time || 0) < 3000 && text.startsWith(last.text)))
      ) {
        list[list.length - 1] = { ...last, id: streamId, text, final: false };
        return list;
      }

      const isDup = list.slice(-2).some((m) => m.role === role && m.text === text);
      if (isDup) return list;

      list.push({ id: streamId, role, text, viaVoice: true, final: false, time: Date.now() });
      return list;
    });
  }, []);

  const finaliseTranscript = useCallback((streamId, text) => {
    setItems((prev) => {
      // Nothing but punctuation came through: drop the bubble entirely.
      if (!/[a-zA-Z0-9]/.test(text)) return prev.filter((m) => m.id !== streamId);
      const list = [...prev];
      const idx = list.findIndex((m) => m.id === streamId);
      if (idx >= 0) list[idx] = { ...list[idx], text, final: true };
      return list;
    });
    setLastActivityAt(Date.now());
  }, []);

  // ── Typed question → REST agent ───────────────────────────────────────

  const handleSendQuery = async (queryText) => {
    const q = queryText?.trim();
    if (!q || isLoading) return;
    setLastActivityAt(Date.now());
    setItems((prev) => [
      ...prev,
      { id: `u_${Date.now()}`, role: 'user', text: q, final: true, time: Date.now() },
    ]);
    setIsLoading(true);

    const { data, error: err } = await api.askAgent(q);
    setIsLoading(false);
    setLastActivityAt(Date.now());

    if (err) {
      setItems((prev) => [
        ...prev,
        { id: `err_${Date.now()}`, role: 'agent', text: `Error: ${err}`, isError: true, final: true, time: Date.now() },
      ]);
      return;
    }
    if (!data) return;

    const next = [
      {
        id: `a_${Date.now()}`,
        role: 'agent',
        text: data.answer,
        tool_used: data.tool_used,
        final: true,
        time: Date.now(),
      },
    ];
    // A chart only comes back for questions that asked to compare or rank
    // something, so when one is here it belongs under the answer.
    if (data.chart?.rows?.length) {
      next.push({
        id: `chart_${Date.now()}`,
        role: 'chart',
        chart: {
          title: data.chart.title,
          rows: data.chart.rows,
          unit: data.chart.unit || 'ms',
          order: data.chart.order || 'best',
        },
        time: Date.now(),
      });
    }
    setItems((prev) => [...prev, ...next]);
  };

  const conversation = (voiceSlot) => (
    <Conversation
      items={items}
      isLoading={isLoading}
      input={input}
      onInputChange={setInput}
      onSendQuery={handleSendQuery}
      onClearItems={() => setItems([])}
      voiceSlot={voiceSlot}
    />
  );

  const idleMicRow = (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        onClick={startVoice}
        disabled={lkConnecting}
        aria-label="Start voice session"
        className="flex items-center justify-center w-10 h-10 shrink-0 rounded-full border-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-cyan-500 hover:text-cyan-700 dark:hover:text-cyan-300 transition-colors active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-wait"
      >
        {lkConnecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mic className="w-4 h-4" />}
      </button>
      <span className="text-[10px] font-mono text-slate-500 dark:text-slate-500">
        {lkConnecting ? 'Connecting to voice session…' : 'Tap the mic to talk instead of typing'}
      </span>
    </div>
  );

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
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[560px] lg:w-[680px] xl:w-[760px] bg-slate-50 dark:bg-[#080e1a] border-l border-slate-200 dark:border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col text-slate-900 dark:text-slate-100 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900/60 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold">
            <Bot className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
            Ask GSH
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-100 dark:bg-cyan-950/80 text-cyan-600 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-800/50 uppercase font-bold">
              AGENT
            </span>
          </div>
          <div className="flex items-center gap-2">
            {lkSession && (
              <span className="hidden sm:inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded-full bg-cyan-100 dark:bg-cyan-950/70 text-cyan-700 dark:text-cyan-300 border border-cyan-300 dark:border-cyan-800/60">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Voice live
              </span>
            )}
            <button
              type="button"
              onClick={handleClose}
              className="p-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {lkError && (
          <div className="mx-4 mt-3 p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 text-[11px] text-rose-700 dark:text-rose-300 flex items-start gap-2 shrink-0">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
            <span>{lkError}</span>
          </div>
        )}

        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          {lkSession ? (
            <LiveKitRoom
              token={lkSession.token}
              serverUrl={lkSession.url}
              connect
              audio
              className="flex-1 flex flex-col min-h-0"
              onDisconnected={() => {
                stopVoice();
              }}
              onError={(err) => {
                setLkError(`Voice connection error: ${err?.message || err}. Please try reconnecting.`);
                stopVoice();
              }}
            >
              <RoomAudioRenderer />
              <VoiceStreamBridge
                onChart={addChart}
                onTranscript={upsertTranscript}
                onFinalise={finaliseTranscript}
                onError={setLkError}
              />
              {conversation(
                <LiveVoiceControls onIdleTimeout={stopVoice} lastActivityAt={lastActivityAt} />
              )}
            </LiveKitRoom>
          ) : (
            conversation(idleMicRow)
          )}
        </div>
      </div>
    </>,
    document.body
  );
}
