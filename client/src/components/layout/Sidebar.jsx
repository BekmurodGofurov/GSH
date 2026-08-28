import React from 'react';
import {
  LayoutDashboard,
  Server,
  Terminal,
  BarChart3,
  Bell,
  Cpu,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { Badge } from '../common/Badge';

export function Sidebar({ currentView, onViewChange, kpis, eventCount, crashCount }) {
  const navItems = [
    {
      id: 'overview',
      label: 'Overview',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: 'servers',
      label: 'Server Fleet',
      icon: Server,
      badge: `${kpis.onlineServers}/${kpis.totalServers}`,
      badgeVariant: 'emerald',
    },
    {
      id: 'events',
      label: 'Event Logs',
      icon: Terminal,
      badge: crashCount > 0 ? `${crashCount} ALERTS` : `${eventCount}`,
      badgeVariant: crashCount > 0 ? 'rose' : 'neutral',
    },
    {
      id: 'analytics',
      label: 'Timescale Analytics',
      icon: BarChart3,
      badge: '1-min',
      badgeVariant: 'cyan',
    },
    {
      id: 'insights',
      label: 'Daily Insights',
      icon: TrendingUp,
      badge: '24h',
      badgeVariant: 'violet',
    },
    {
      id: 'alerting',
      label: 'Alerting Config',
      icon: Bell,
      badge: null,
    },
  ];

  return (
    <aside className="w-64 flex-shrink-0 border-r border-slate-800/80 bg-slate-950/60 backdrop-blur-2xl flex flex-col justify-between hidden md:flex min-h-[calc(100vh-61px)]">
      {/* Navigation Links */}
      <div className="p-4 space-y-1.5">
        <div className="px-3 py-2 text-[10px] font-bold font-mono tracking-widest text-slate-400 uppercase">
          OPERATIONAL CONTROL
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                'w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-150 group text-left cursor-pointer',
                isActive
                  ? 'bg-gradient-to-r from-cyan-500/15 to-blue-500/10 text-cyan-300 border border-cyan-500/30 shadow-glow font-semibold'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/80 border border-transparent'
              )}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={cn(
                    'w-4 h-4 transition-colors',
                    isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-slate-200'
                  )}
                />
                <span>{item.label}</span>
              </div>

              {item.badge && (
                <Badge
                  variant={item.badgeVariant || 'neutral'}
                  size="sm"
                  className="text-[10px] px-1.5 py-0"
                >
                  {item.badge}
                </Badge>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Telemetry Info Box */}
      <div className="p-4 m-3 rounded-xl border border-slate-800 bg-slate-900/60 text-xs">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-[11px] font-mono">
          <span className="text-slate-400 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            TARGET REGION
          </span>
          <span className="text-cyan-400 font-semibold">EU-EAST</span>
        </div>

        <div className="space-y-1.5 font-mono text-[11px]">
          <div className="flex justify-between text-slate-400">
            <span>Vienna Hub:</span>
            <span className="text-emerald-400">ONLINE</span>
          </div>
          <div className="flex justify-between text-slate-400">
            <span>Warsaw Hub:</span>
            <span className="text-emerald-400">ONLINE</span>
          </div>
          <div className="flex justify-between text-slate-400">
            <span>Health Score:</span>
            <span className={kpis.healthIndex > 80 ? 'text-emerald-400' : 'text-amber-400'}>
              {kpis.healthIndex}%
            </span>
          </div>
        </div>

        <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-400" /> A2S Poller v1.0
          </span>
          <span className="font-mono text-cyan-400">Port 27015</span>
        </div>
      </div>
    </aside>
  );
}
