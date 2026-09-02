import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Web Audio API synthesizer for alert sound effects without requiring external audio assets.
 */
export function useAudioAlert() {
  const [isMuted, setIsMuted] = useState(() => {
    const saved = localStorage.getItem('cs2_monitor_muted');
    return saved !== null ? JSON.parse(saved) : true;
  });

  const audioCtxRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('cs2_monitor_muted', JSON.stringify(isMuted));
  }, [isMuted]);

  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        audioCtxRef.current = new AudioCtx();
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }, []);

  const playTone = useCallback((frequency = 440, duration = 0.15, type = 'sine') => {
    if (isMuted) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(frequency, ctx.currentTime);

      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + duration);
    } catch (e) {
      console.warn('Audio tone could not play:', e);
    }
  }, [isMuted, getAudioContext]);

  const triggerAlert = useCallback((eventType) => {
    if (isMuted) return;
    const type = (eventType || '').toUpperCase();
    if (type === 'CRASH' || type === 'OFFLINE') {
      // Urgent double beep
      playTone(220, 0.12, 'sawtooth');
      setTimeout(() => playTone(180, 0.25, 'sawtooth'), 150);
    } else if (type === 'HIGH_PING' || type === 'WARNING') {
      playTone(360, 0.2, 'triangle');
    } else if (type === 'RECOVERY') {
      // Pleasant upward chime
      playTone(523.25, 0.1, 'sine'); // C5
      setTimeout(() => playTone(659.25, 0.15, 'sine'), 100); // E5
    }
  }, [isMuted, playTone]);

  const toggleMute = () => setIsMuted((prev) => !prev);

  return {
    isMuted,
    toggleMute,
    triggerAlert,
    playTestTone: () => playTone(587.33, 0.15, 'sine'),
  };
}
