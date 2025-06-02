// Environment configuration for the OASIS frontend application
// This file centralizes all environment-dependent settings

export const config = {
  // API Configuration
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  
  // Application Settings
  APP_TITLE: import.meta.env.VITE_APP_TITLE || 'OASIS',
  APP_VERSION: import.meta.env.VITE_APP_VERSION || '1.0.0',
  
  // Development Settings
  LOG_LEVEL: import.meta.env.VITE_LOG_LEVEL || 'info',
  IS_DEVELOPMENT: import.meta.env.DEV,
  IS_PRODUCTION: import.meta.env.PROD,
  
  // API Endpoints
  API_ENDPOINTS: {
    DATA: '/api/data',
    VESSEL_TYPES: '/api/data/vessel_types',
    TANKS: '/api/data/tanks',
    VESSELS: '/api/data/vessels',
    CRUDES: '/api/data/crudes',
    RECIPES: '/api/data/recipes',
    PLANTS: '/api/data/plants',
    ROUTES: '/api/data/routes',
    SCHEDULER_RUN: '/api/scheduler/run',
    OPTIMIZER_OPTIMIZE: '/api/optimizer/optimize',
    VESSEL_OPTIMIZER: '/api/vessel-optimizer/optimize',
    EVENTS: '/events'
  },
  
  // Timeouts and Intervals
  API_TIMEOUT: 30000, // 30 seconds
  HEARTBEAT_INTERVAL: 30000, // 30 seconds for SSE heartbeat
  POLLING_INTERVAL: 5000, // 5 seconds for data polling
  
  // UI Settings
  TOAST_DURATION: 3000, // 3 seconds for success messages
  ERROR_TOAST_DURATION: 5000, // 5 seconds for error messages
}

// Helper function to get full API URL
export const getApiUrl = (endpoint) => {
  return `${config.API_BASE_URL}${endpoint}`
}

// Helper function for logging (respects LOG_LEVEL)
export const logger = {
  debug: (...args) => {
    if (['debug'].includes(config.LOG_LEVEL)) {
      console.log('[DEBUG]', ...args)
    }
  },
  info: (...args) => {
    if (['debug', 'info'].includes(config.LOG_LEVEL)) {
      console.info('[INFO]', ...args)
    }
  },
  warn: (...args) => {
    if (['debug', 'info', 'warn'].includes(config.LOG_LEVEL)) {
      console.warn('[WARN]', ...args)
    }
  },
  error: (...args) => {
    console.error('[ERROR]', ...args)
  }
}

export default config
