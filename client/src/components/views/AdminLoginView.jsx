import React, { useState } from 'react';
import { ShieldCheck, Lock, User, ArrowLeft, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../../services/api';
import { Card, CardContent } from '../common/Card';
import { Button } from '../common/Button';
import { Input } from '../common/Input';

export function AdminLoginView({ onLoginSuccess, onExitAdmin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please provide both username and password.');
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const res = await api.adminLogin(username, password);
      if (res.error) {
        setError(res.error || 'Authentication failed. Please verify credentials.');
      } else {
        onLoginSuccess();
      }
    } catch (err) {
      setError('An unexpected error occurred during authentication.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
      <div className="w-full max-w-md">
        {/* Back navigation */}
        {onExitAdmin && (
          <div className="mb-4">
            <button
              type="button"
              onClick={onExitAdmin}
              className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-500 hover:text-cyan-600 dark:text-slate-400 dark:hover:text-cyan-400 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Return to Public Telemetry Monitor
            </button>
          </div>
        )}

        <Card className="border-cyan-500/30 shadow-2xl shadow-cyan-950/20 dark:shadow-[0_0_40px_rgba(6,182,212,0.12)]">
          <CardContent className="p-6 sm:p-8">
            {/* Header Icon */}
            <div className="flex flex-col items-center text-center mb-6">
              <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400 mb-3 shadow-[0_0_20px_rgba(6,182,212,0.2)]">
                <ShieldCheck className="w-7 h-7" />
              </div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                Fleet Administration Login
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                Restricted access console for managing Counter-Strike 2 telemetry nodes and poller targets.
              </p>
            </div>

            {/* Error Notification */}
            {error && (
              <div className="mb-5 p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 text-rose-700 dark:text-rose-400 text-xs flex items-start gap-2 animate-fade-in">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                  Admin Username
                </label>
                <Input
                  icon={User}
                  type="text"
                  placeholder="Enter administrator username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isLoading}
                  autoComplete="username"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                  Access Key / Password
                </label>
                <Input
                  icon={Lock}
                  type="password"
                  placeholder="Enter access password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  autoComplete="current-password"
                  required
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full justify-center py-2.5 font-semibold text-sm"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Authenticating...
                    </span>
                  ) : (
                    'Authenticate Terminal'
                  )}
                </Button>
              </div>
            </form>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400 dark:text-slate-500">
              <span>A2S SECURE SESSION</span>
              <span className="text-emerald-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span> ENCRYPTED
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

