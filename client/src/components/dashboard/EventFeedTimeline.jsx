import React, { useState } from 'react';
import {
  Terminal,
  AlertTriangle,
  CheckCircle2,
  Flame,
  Clock,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { formatTime, formatRelativeTime, formatEventBadge } from '../../utils/formatters';

export function EventFeedTimeline({ events = [], onSelectServer }) {
  const [filterType, setFilterType] = useState('ALL');

  const filteredEvents = events.filter((e) => {
    if (filterType === 'ALL') return true;
    return (e.event_type || '').toUpperCase() === filterType;
  });

  return (
    <Card className="border-slate-800/80">
      <CardHeader className="flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <CardTitle icon={Terminal}>Live System Incidents & Event Feed</CardTitle>
          <Badge variant="rose" dot size="sm">
            {events.length} LOGS
          </Badge>
        </div>

        {/* Severity Filter Tabs */}
        <div className="flex items-center rounded-lg bg-slate-950/80 border border-slate-800 p-0.5 text-xs font-mono">
          {['ALL', 'CRASH', 'HIGH_PING', 'RECOVERY'].map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-2 py-1 rounded-md transition-all ${
                filterType === type
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="max-h-[380px] overflow-y-auto divide-y divide-slate-800/60 font-mono text-xs">
          {filteredEvents.length === 0 ? (
            <div className="p-8 text-center text-slate-400">
              No events match the selected filter.
            </div>
          ) : (
            filteredEvents.map((evt) => {
              const badge = formatEventBadge(evt.event_type);
              const isCrash = (evt.event_type || '').toUpperCase() === 'CRASH';

              return (
                <div
                  key={evt.id || `${evt.server_id}-${evt.time}`}
                  className={`p-3.5 sm:p-4 hover:bg-slate-800/40 transition-colors flex items-start gap-3.5 ${
                    isCrash ? 'bg-rose-950/10' : ''
                  }`}
                >
                  {/* Icon Indicator */}
                  <div className="mt-0.5">
                    {isCrash ? (
                      <div className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
                        <Flame className="w-4 h-4" />
                      </div>
                    ) : (evt.event_type || '').toUpperCase() === 'RECOVERY' ? (
                      <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                        <CheckCircle2 className="w-4 h-4" />
                      </div>
                    ) : (
                      <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/40">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                    )}
                  </div>

                  {/* Body */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <Badge variant={badge.variant} size="sm">
                          {badge.label}
                        </Badge>
                        <button
                          onClick={() => onSelectServer && onSelectServer(evt.server_id)}
                          className="font-bold text-slate-200 hover:text-cyan-400 hover:underline transition-colors"
                        >
                          {evt.server_id}
                        </button>
                      </div>

                      <div className="flex items-center gap-2 text-[11px] text-slate-400">
                        <Clock className="w-3 h-3 text-slate-400" />
                        <span>{formatRelativeTime(evt.time)}</span>
                        <span className="text-slate-400">({formatTime(evt.time)})</span>
                      </div>
                    </div>

                    <p className="text-slate-300 text-xs font-sans mt-1 leading-relaxed">
                      {evt.message}
                    </p>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}
