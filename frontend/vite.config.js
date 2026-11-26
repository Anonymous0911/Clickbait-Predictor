import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const target = process.env.VITE_PROXY_TARGET || 'http://localhost:8000';
// changeOrigin stays false so Django sees Host localhost:5173 and the CSRF origin check passes.
const proxy = { target, changeOrigin: false, xfwd: true };

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': proxy, '/admin': proxy, '/static': proxy },
  },
});
