import React from 'react';
import { X, Flame, AlertOctagon, Activity, CheckCircle2, Info, ExternalLink, Bell, Trash2 } from 'lucide-react';
import { formatTime, formatRelativeTime } from '../../utils/formatters';

function getToastConfig(eventType) {
  const type = (eventType || '').toUpperCase();
  switch (type) {
    case 'CRASH':
      return { icon: Flame, textClass: 'text-rose-500' };
    case 'OFFLINE':
      return { icon: AlertOctagon, textClass: 'text-rose-500' };
    case 'HIGH_PING':
    case 'WARNING':
      return { icon: Activity, textClass: 'text-amber-500' };
    case 'RECOVERY':
    case 'ONLINE':
      return { icon: CheckCircle2, textClass: 'text-emerald-500' };
    default:
      return { icon: Info, textClass: 'text-cyan-500' };
  }
}

export function NotificationsDrawer({ isOpen, onClose, notifications = [], onInspect, onClearAll }) {
  // Sort notifications by date descending
  const sorted = [...notifications].sort((a, b) => new Date(b.time) - new Date(a.time));

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}
      
      {/* Drawer */}
      <div 
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold">
            <Bell className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
            Notifications
            {notifications.length > 0 && (
              <span className="bg-cyan-100 text-cyan-700 dark:bg-cyan-900/50 dark:text-cyan-300 py-0.5 px-2 rounded-full text-xs font-mono">
                {notifications.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {notifications.length > 0 && (
              <button 
                onClick={onClearAll}
                className="p-1.5 text-slate-400 hover:text-rose-500 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
                title="Clear all"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            <button 
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/50 dark:bg-slate-950">
          {sorted.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 dark:text-slate-400">
              <Bell className="w-12 h-12 mb-4 opacity-20" />
              <p className="text-sm">No new notifications</p>
            </div>
          ) : (
            sorted.map((notif) => {
              const { icon: Icon, textClass } = getToastConfig(notif.event_type);
              
              return (
                <div key={notif.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-2">
                      <Icon className={`w-4 h-4 ${textClass}`} />
                      <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 line-clamp-1">
                        {notif.server_name || notif.server_id}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono whitespace-nowrap ml-2">
                      {formatRelativeTime(notif.time)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mb-2 line-clamp-2">
                    {notif.message}
                  </p>
                  {onInspect && notif.server_id && (
                    <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 font-mono">{formatTime(notif.time)}</span>
                      <button
                        onClick={() => {
                          onInspect(notif.server_id);
                          onClose();
                        }}
                        className="text-[11px] font-mono text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 flex items-center gap-1 transition-colors font-medium"
                      >
                        Inspect <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
