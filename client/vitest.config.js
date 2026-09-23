import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// A config of its own, deliberately not vite.config.js: that one throws when
// VITE_API_URL / CLIENT_PORT are unset, which would make the test run depend on
// a developer's local .env. Vitest picks this file up ahead of vite.config.js.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    // src/services/api.js throws at import time without this.
    env: {
      VITE_API_URL: 'http://localhost:8000',
      VITE_WS_URL: 'ws://localhost:8000/ws/live',
      VITE_ADMIN_PATH: '/secret-admin',
    },
  },
});
