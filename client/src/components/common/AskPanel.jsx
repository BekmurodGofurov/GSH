import React, { useState, useRef, useEffect } from 'react';
import { X, Bot, Send, Loader2, Wrench, AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';

export function AskPanel({ isOpen, onClose }) {
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState(null);   // { answer, tool_used }
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  // Focus the textarea whenever the panel opens
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // Allow Escape key to close the panel
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

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

  // Allow Ctrl+Enter or Cmd+Enter to submit from the textarea
  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSubmit(e);
    }
  }

  return (
    <>
      {/* Dark backdrop — clicking it closes the panel */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* The panel itself */}
      <div
        className={`fixed inset-y-0 right-0 z-50 w-full sm:w-[420px] bg-white dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header bar */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-bold">
            <Bot className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
            Ask GSH
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800/50 uppercase font-bold">
              AGENT
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50 dark:bg-slate-950">

          {/* Prompt hints when nothing has been asked yet */}
          {!response && !error && !isLoading && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium uppercase tracking-wider">
                Try asking:
              </p>
              {[
                'What is the average latency right now?',
                'Which servers are currently offline?',
                'What happened in the last 10 events?',
                'Re-label event 5 as HIGH_LATENCY',
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

          {/* Loading state */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500 dark:text-slate-400 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
              <p className="text-sm">Agent is thinking…</p>
            </div>
          )}

          {/* Error state */}
          {error && !isLoading && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800">
              <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-rose-700 dark:text-rose-400">
                  Something went wrong
                </p>
                <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Agent response */}
          {response && !isLoading && (
            <div className="space-y-3">
              {/* The tool that was called — proof for the demo */}
              {response.tool_used && (
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 font-mono">
                  <Wrench className="w-3.5 h-3.5 text-cyan-500" />
                  <span>
                    Tool used:{' '}
                    <span className="text-cyan-600 dark:text-cyan-400 font-semibold">
                      {response.tool_used}
                    </span>
                  </span>
                </div>
              )}

              {/* The answer text */}
              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                <p className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {response.answer}
                </p>
              </div>

              {/* Ask again button */}
              <button
                onClick={() => { setResponse(null); setError(null); setQuestion(''); }}
                className="text-xs text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 transition-colors"
              >
                ← Ask another question
              </button>
            </div>
          )}
        </div>

        {/* Fixed input area at the bottom */}
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
              rows={3}
              disabled={isLoading}
              className="w-full resize-none rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm px-3 py-2.5 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-400 dark:focus:border-cyan-600 disabled:opacity-50 transition-colors"
            />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-mono">
                Ctrl+Enter to send
              </span>
              <button
                type="submit"
                disabled={isLoading || !question.trim()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-300 dark:disabled:bg-slate-700 text-white disabled:text-slate-500 text-xs font-semibold transition-colors"
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                Send
              </button>
            </div>
          </div>
        </form>
      </div>
    </>
  );
}