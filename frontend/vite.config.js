import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  // Backend API URL configuration
  const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:5001'
  
  return {
    plugins: [react(), tailwindcss()],
    
    // Define global constants for the app
    define: {
      __API_BASE_URL__: JSON.stringify(API_BASE_URL),
    },
    
    // Development server configuration
    server: {
      host: '0.0.0.0', // Allow external connections
      port: 5173,
      strictPort: true, // Exit if port is already in use
      
      // Proxy configuration for API requests
      proxy: {
        '/api': {
          target: API_BASE_URL,
          changeOrigin: true,
          secure: false,
          timeout: 30000, // 30 second timeout
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.log('Proxy error:', err);
            });
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log('Proxying request:', req.method, req.url);
            });
          }
        },
        
        // Proxy for Server-Sent Events (SSE)
        '/events': {
          target: API_BASE_URL,
          changeOrigin: true,
          secure: false,
          ws: true, // Enable WebSocket proxying
        }
      },
    },
    
    // Preview server configuration (for production builds)
    preview: {
      host: '0.0.0.0',
      port: 4173,
      strictPort: true,
      
      // Same proxy configuration for preview
      proxy: {
        '/api': {
          target: API_BASE_URL,
          changeOrigin: true,
          secure: false,
        },
        '/events': {
          target: API_BASE_URL,
          changeOrigin: true,
          secure: false,
          ws: true,
        }
      },
    },
    
    // Build configuration
    build: {
      outDir: 'dist',
      sourcemap: mode === 'development',
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            utils: ['axios'], // If you're using axios
          },
        },
      },
    },
    
    // Environment variables
    envPrefix: 'VITE_',
  }
})
