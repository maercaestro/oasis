#!/usr/bin/env node
// Simple API connectivity test script for OASIS frontend

import axios from 'axios'

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:5001'

const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m'
}

const log = (color, ...args) => console.log(color, ...args, colors.reset)

const testEndpoint = async (name, endpoint) => {
  try {
    const startTime = Date.now()
    const response = await axios.get(`${API_BASE_URL}${endpoint}`, {
      timeout: 10000
    })
    const duration = Date.now() - startTime
    
    log(colors.green, `✓ ${name}: OK (${duration}ms)`)
    return true
  } catch (error) {
    log(colors.red, `✗ ${name}: FAILED`)
    log(colors.red, `  Error: ${error.message}`)
    return false
  }
}

const main = async () => {
  log(colors.blue, '🧪 Testing OASIS API connectivity...')
  log(colors.blue, `📡 API Base URL: ${API_BASE_URL}`)
  console.log()

  const tests = [
    ['Main Data Endpoint', '/api/data'],
    ['Vessel Types', '/api/data/vessel_types'],
    ['Tanks', '/api/data/tanks'],
    ['Vessels', '/api/data/vessels'],
    ['Crudes', '/api/data/crudes'],
    ['Recipes', '/api/data/recipes'],
    ['Plants', '/api/data/plants'],
    ['Routes', '/api/data/routes']
  ]

  let passed = 0
  let total = tests.length

  for (const [name, endpoint] of tests) {
    const success = await testEndpoint(name, endpoint)
    if (success) passed++
  }

  console.log()
  if (passed === total) {
    log(colors.green, `🎉 All tests passed! (${passed}/${total})`)
    log(colors.green, '✅ Backend API is ready for frontend integration')
  } else {
    log(colors.yellow, `⚠️  Some tests failed (${passed}/${total})`)
    log(colors.yellow, '❌ Please check backend server status')
  }
}

main().catch(error => {
  log(colors.red, '💥 Test runner failed:', error.message)
  process.exit(1)
})
