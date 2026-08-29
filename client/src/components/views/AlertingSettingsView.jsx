import React, { useState } from 'react';
import {
  Bell,
  Send,
  Sliders,
  CheckCircle2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Input } from '../common/Input';

export function AlertingSettingsView({ audio, onTriggerTestAlert }) {
  const [webhookUrl, setWebhookUrl] = useState(
    'https://discord.com/api/webhooks/1234567890/sample-token'
  );
  const [pingThreshold, setPingThreshold] = useState(75);
  const [crashNotification, setCrashNotification] = useState(true);
  const [testSent, setTestSent] = useState(false);

  const handleTestWebhook = () => {
    setTestSent(true);
    setTimeout(() => setTestSent(false), 4000);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
          <Bell className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
          Alerting & Incident Dispatch Settings
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-mono">
          Configure real-time Discord notifications and anomaly thresholds for the alerting service.
        </p>
      </div>

      {/* Discord Webhook Card */}
      <Card className="border-slate-200/80 dark:border-slate-800/80">
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <CardTitle icon={Send}>Discord Ops Channel Webhook</CardTitle>
            <Badge variant="emerald" size="sm">
              ACTIVE
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-slate-700 dark:text-slate-300 mb-1.5 font-medium">
              DISCORD WEBHOOK URL
            </label>
            <Input
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://discord.com/api/webhooks/..."
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
              Sends instant embedded alert cards to game ops discord when server drops below SLA.
            </span>
            <Button
              variant="primary"
              size="sm"
              icon={Send}
              onClick={handleTestWebhook}
            >
              Dispatch Test Alert
            </Button>
          </div>

          {testSent && (
            <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-200 dark:border-emerald-500/50 text-emerald-800 dark:text-emerald-300 font-mono text-xs flex items-center gap-2 animate-fade-in shadow-xs dark:shadow-none">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Test payload dispatched: "CS2 Pulse [CRASH Alert Simulator] verified connection."
            </div>
          )}
        </CardContent>
      </Card>

      {/* Anomaly Detection Thresholds */}
      <Card className="border-slate-200/80 dark:border-slate-800/80">
        <CardHeader>
          <CardTitle icon={Sliders}>Telemetry Trigger Thresholds</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Latency Threshold */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-mono text-slate-700 dark:text-slate-300 font-medium">
                HIGH LATENCY ALERT TRIGGER
              </label>
              <span className="text-sm font-bold font-mono text-cyan-700 dark:text-cyan-400">
                &gt; {pingThreshold} ms
              </span>
            </div>
            <input
              type="range"
              min="30"
              max="200"
              value={pingThreshold}
              onChange={(e) => setPingThreshold(e.target.value)}
              className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
            />
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono mt-1">
              Triggers a WARNING event if average server ping exceeds this value for 2 consecutive polls.
            </p>
          </div>

          {/* Crash Alert Toggle */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-800">
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">Instant Crash Alerting</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                Notify immediately when player count drops from &gt;5 to 0 mid-match or A2S times out.
              </p>
            </div>
            <button
              onClick={() => setCrashNotification(!crashNotification)}
              className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors cursor-pointer ${
                crashNotification ? 'bg-cyan-500 justify-end' : 'bg-slate-300 dark:bg-slate-800 justify-start'
              }`}
            >
              <span className="w-4 h-4 rounded-full bg-white dark:bg-slate-950 shadow-md transform" />
            </button>
          </div>

          {/* Audio Alert & Live Notification Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-slate-200 dark:border-slate-800">
            <div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">Operator Sound & Live Toast Alerts</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                Audio chime + top-right interactive notification on incoming crash/latency incidents.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {onTriggerTestAlert && (
                <>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => onTriggerTestAlert('CRASH')}
                    title="Simulate a CRASH alert"
                  >
                    Test Crash Alert
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onTriggerTestAlert('HIGH_PING')}
                    title="Simulate a HIGH PING alert"
                  >
                    Test Latency Alert
                  </Button>
                </>
              )}
              <Button
                variant={audio.isMuted ? 'outline' : 'emerald'}
                size="sm"
                onClick={audio.toggleMute}
              >
                {audio.isMuted ? 'Muted' : 'Audible'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
