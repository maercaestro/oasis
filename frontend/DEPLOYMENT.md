# OASIS Frontend Deployment Configuration

## Quick Start Commands

### Development
```bash
# Start development server (default port 5173)
npm run dev

# Start development server with external access
npm run dev:host

# Test API connectivity
npm run test:api
```

### Production Build
```bash
# Build for production
npm run build:prod

# Build for development (with source maps)
npm run build:dev

# Preview production build
npm run preview

# Preview with external access
npm run preview:host
```

## Environment Configuration

### Environment Variables
The application uses environment variables prefixed with `VITE_`:

- `VITE_API_BASE_URL`: Backend API URL (default: http://localhost:5001)
- `VITE_APP_TITLE`: Application title
- `VITE_APP_VERSION`: Application version
- `VITE_LOG_LEVEL`: Logging level (debug, info, warn, error)

### Environment Files
- `.env.development`: Development environment settings
- `.env.production`: Production environment settings
- `.env.local`: Local overrides (create from .env.example)

## Proxy Configuration

### Development Proxy
All `/api` requests are automatically proxied to the backend server:
- API requests: `http://localhost:5173/api/*` → `http://localhost:5001/api/*`
- SSE events: `http://localhost:5173/events` → `http://localhost:5001/events`

### Production Deployment
For production, you have several options:

#### Option 1: Same Server Deployment
Deploy frontend and backend on the same server:
```bash
# Build frontend
npm run build:prod

# Serve from backend static files or use nginx
```

#### Option 2: Separate Server Deployment
Deploy frontend and backend on different servers:
```bash
# Set API URL for production
export VITE_API_BASE_URL=https://your-api-server.com
npm run build:prod
```

#### Option 3: Docker Deployment
```dockerfile
# Frontend Dockerfile example
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build:prod
EXPOSE 4173
CMD ["npm", "run", "preview:host"]
```

## Testing

### API Connectivity Test
```bash
npm run test:api
```

### Manual Testing Checklist
1. ✅ Frontend loads without errors
2. ✅ API connectivity established
3. ✅ Data editors load and display data
4. ✅ Save operations work correctly
5. ✅ Error handling works properly

## Troubleshooting

### Common Issues

#### CORS Errors
- Ensure backend has proper CORS configuration
- Check that `Access-Control-Allow-Origin` includes frontend URL

#### Proxy Not Working
- Verify backend server is running on correct port
- Check vite.config.js proxy configuration
- Restart development server after config changes

#### Environment Variables Not Loading
- Ensure variables are prefixed with `VITE_`
- Restart development server after changing .env files
- Check that .env files are in the correct location

#### Build Failures
- Clear node_modules and reinstall dependencies
- Check for TypeScript/ESLint errors
- Verify all imports are correct

### Performance Optimization

#### Bundle Analysis
```bash
# Add bundle analyzer
npm install --save-dev rollup-plugin-visualizer

# Analyze bundle size
npm run build && npx vite-bundle-analyzer dist
```

#### Caching Strategy
- API responses are not cached by default
- Consider implementing client-side caching for static data
- Use React Query or SWR for advanced caching

## Security Considerations

### Environment Variables
- Never commit .env.local files
- Use different API keys/secrets for different environments
- Validate all environment variables on startup

### API Security
- Implement proper authentication if needed
- Validate all API responses
- Handle errors gracefully without exposing internal details

### Content Security Policy
Consider implementing CSP headers for production:
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';">
```
