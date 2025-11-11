import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 3000,
    open: true,
    middlewareMode: false
  },
  build: {
    target: 'esnext'
  },
  optimizeDeps: {
    exclude: ['marisa.js']
  },
  assetsInclude: ['**/*.wasm', '**/*.bin', '**/*.gz'],
  plugins: [
    {
      name: 'configure-server',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // Don't add Content-Encoding for .gz files - we'll decompress in JS
          if (req.url?.endsWith('.gz')) {
            res.setHeader('Content-Type', 'application/octet-stream');
          }
          next();
        });
      }
    }
  ]
});
