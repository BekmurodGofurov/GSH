import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const targetApi = env.VITE_API_URL;
  const targetWs = env.VITE_WS_URL ? env.VITE_WS_URL.replace('/ws/live', '') : (targetApi ? targetApi.replace('http', 'ws') : null);

  if (!targetApi) {
    throw new Error("VITE_API_URL environment variable is not set in client/.env");
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      host: true,
      proxy: {
        '/api': {
          target: targetApi,
          changeOrigin: true,
        },
        '/ws': {
          target: targetWs,
          ws: true,
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/recharts')) {
              return 'charts';
            }
            if (id.includes('node_modules/lucide-react')) {
              return 'icons';
            }
          },
        },
      },
    },
  };
});
