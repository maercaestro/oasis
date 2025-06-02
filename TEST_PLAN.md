# OASIS System Test Plan

## Overview
This document outlines the comprehensive testing strategy for the OASIS (Oil & Gas Analytics System Integrated Solution) before deployment. The system consists of a Flask backend with SQLite database and a React frontend.

## Test Environment Setup

### Prerequisites
- Backend Flask server running on `http://localhost:5001`
- Frontend React development server running on `http://localhost:5173`
- SQLite database (`oasis.db`) properly migrated
- All dependencies installed

### Quick Setup Commands
```bash
# Backend
cd backend && python api.py

# Frontend (in another terminal)
cd frontend && npm run dev
```

## Test Categories

### 1. Database and API Foundation Tests

#### 1.1 Database Connection and Schema
- [ ] **Test**: Database file exists at `backend/oasis.db`
- [ ] **Test**: All required tables are created (tanks, vessels, crudes, recipes, vessel_types, etc.)
- [ ] **Test**: Database migration completed (`.migration_completed` flag exists)

**Commands to verify:**
```bash
cd backend
sqlite3 oasis.db ".tables"
sqlite3 oasis.db ".schema vessel_types"
ls -la .migration_completed
```

#### 1.2 Basic API Health
- [ ] **Test**: Flask server starts without errors
- [ ] **Test**: CORS is properly configured
- [ ] **Test**: API returns JSON responses

**Commands to test:**
```bash
curl http://localhost:5001/api/data
curl -i http://localhost:5001/api/data/tanks
```

### 2. Data CRUD Operations Tests

#### 2.1 Vessel Types (Recently Fixed Feature)
- [ ] **Test**: GET `/api/data/vessel_types` returns data with name, capacity, and cost
- [ ] **Test**: POST `/api/data/vessel_types` saves new vessel types
- [ ] **Test**: Saved vessel types persist after server restart
- [ ] **Test**: Main `/api/data` endpoint includes vessel_types with names

**Test Commands:**
```bash
# Get current vessel types
curl http://localhost:5001/api/data/vessel_types

# Save new vessel types
curl -X POST -H "Content-Type: application/json" \
  -d '[{"name": "Test Large", "capacity": 900, "cost": 100000}, {"name": "Test Small", "capacity": 200, "cost": 30000}]' \
  http://localhost:5001/api/data/vessel_types

# Verify persistence
curl http://localhost:5001/api/data/vessel_types

# Check main data endpoint
curl -s http://localhost:5001/api/data | jq '.vessel_types'
```

#### 2.2 Tanks Data
- [ ] **Test**: GET `/api/data/tanks` returns tank data
- [ ] **Test**: POST `/api/data/tanks` saves tank modifications
- [ ] **Test**: Individual tank operations (GET, PUT, DELETE `/api/data/tanks/<name>`)
- [ ] **Test**: Tank content (crude grades and volumes) are properly saved

**Test Commands:**
```bash
curl http://localhost:5001/api/data/tanks
curl -X POST -H "Content-Type: application/json" \
  -d '{"TestTank": {"capacity": 1000, "content": [{"grade": "Brent", "volume": 500}]}}' \
  http://localhost:5001/api/data/tanks
```

#### 2.3 Vessels Data
- [ ] **Test**: GET `/api/data/vessels` returns vessel data
- [ ] **Test**: POST `/api/data/vessels` saves vessel modifications
- [ ] **Test**: Vessel cargo data is preserved
- [ ] **Test**: Vessel routes and arrival schedules are maintained

#### 2.4 Crudes Data
- [ ] **Test**: GET `/api/data/crudes` returns crude oil data
- [ ] **Test**: POST `/api/data/crudes` saves crude modifications
- [ ] **Test**: Crude properties (margin, origin) are preserved

#### 2.5 Recipes Data
- [ ] **Test**: GET `/api/data/recipes` returns blending recipes
- [ ] **Test**: POST `/api/data/recipes` saves recipe modifications
- [ ] **Test**: Recipe components and fractions are accurate

#### 2.6 Plants Data
- [ ] **Test**: GET `/api/data/plants` returns plant configuration
- [ ] **Test**: Plant capacity and constraints are correct

#### 2.7 Routes Data
- [ ] **Test**: GET `/api/data/routes` returns shipping routes
- [ ] **Test**: Route distances and travel times are accurate

### 3. Frontend Integration Tests

#### 3.1 Data Loading
- [ ] **Test**: Frontend loads all data types on startup
- [ ] **Test**: Loading states are properly displayed
- [ ] **Test**: Error states are handled gracefully
- [ ] **Test**: Data refresh functionality works

#### 3.2 Data Editor Components
- [ ] **Test**: Tank editor loads and displays tank data
- [ ] **Test**: Vessel editor shows vessel information and cargo
- [ ] **Test**: Crude editor displays crude properties
- [ ] **Test**: Recipe editor shows blending recipes with components
- [ ] **Test**: Vessel Types editor displays name, capacity, and cost fields
- [ ] **Test**: Plants editor shows plant configurations
- [ ] **Test**: Routes editor displays shipping routes

#### 3.3 Data Saving
- [ ] **Test**: Save buttons work for all data types
- [ ] **Test**: Success messages appear after successful saves
- [ ] **Test**: Error messages show for failed saves
- [ ] **Test**: Data persists after page refresh

#### 3.4 Real-time Updates (SSE)
- [ ] **Test**: Server-Sent Events connection establishes
- [ ] **Test**: Data changes notify other connected clients
- [ ] **Test**: Heartbeat messages keep connection alive

### 4. Scheduler and Optimization Tests

#### 4.1 Basic Scheduler
- [ ] **Test**: POST `/api/scheduler/run` executes without errors
- [ ] **Test**: Scheduler uses database data (tanks, vessels, crudes)
- [ ] **Test**: Generated schedule is saved to output file
- [ ] **Test**: Schedule data is returned in API response

#### 4.2 Schedule Optimizer
- [ ] **Test**: POST `/api/optimizer/optimize` runs optimization
- [ ] **Test**: Optimizer improves schedule metrics
- [ ] **Test**: Optimized schedule maintains feasibility

#### 4.3 Vessel Optimizer
- [ ] **Test**: POST `/api/vessel-optimizer/optimize` optimizes vessel schedules
- [ ] **Test**: Vessel optimization reduces total costs
- [ ] **Test**: Optimized vessels meet feedstock requirements

### 5. Data Consistency and Integrity Tests

#### 5.1 Database Transactions
- [ ] **Test**: Failed saves don't corrupt database
- [ ] **Test**: Concurrent saves are handled properly
- [ ] **Test**: Database locks don't cause deadlocks

#### 5.2 Data Relationships
- [ ] **Test**: Tank contents reference valid crude grades
- [ ] **Test**: Vessel cargo references valid crude grades
- [ ] **Test**: Recipe components use valid crude grades
- [ ] **Test**: Feedstock parcels are extracted from vessel cargo

#### 5.3 Data Validation
- [ ] **Test**: Negative values are handled appropriately
- [ ] **Test**: Empty or null data doesn't crash the system
- [ ] **Test**: Invalid JSON payloads return proper error messages

### 6. Performance and Load Tests

#### 6.1 Response Times
- [ ] **Test**: GET `/api/data` responds within 2 seconds
- [ ] **Test**: Individual endpoint responses are under 1 second
- [ ] **Test**: Save operations complete within 5 seconds

#### 6.2 Data Volume
- [ ] **Test**: System handles 100+ tanks
- [ ] **Test**: System handles 50+ vessels with full cargo
- [ ] **Test**: Large schedule data (30+ days) loads properly

### 7. Error Handling and Edge Cases

#### 7.1 API Error Handling
- [ ] **Test**: Invalid endpoints return 404
- [ ] **Test**: Malformed JSON returns 400
- [ ] **Test**: Database errors return 500 with meaningful messages
- [ ] **Test**: CORS preflight requests are handled

#### 7.2 Frontend Error Handling
- [ ] **Test**: API connection failures show user-friendly messages
- [ ] **Test**: Invalid data input is validated client-side
- [ ] **Test**: Network timeouts are handled gracefully

#### 7.3 Edge Cases
- [ ] **Test**: Empty database tables don't crash the system
- [ ] **Test**: Missing configuration files fall back to defaults
- [ ] **Test**: Server restart doesn't lose data

### 8. Security Tests

#### 8.1 Input Validation
- [ ] **Test**: SQL injection attempts are prevented
- [ ] **Test**: XSS attempts are sanitized
- [ ] **Test**: File upload restrictions (if any) are enforced

#### 8.2 CORS and Headers
- [ ] **Test**: Only allowed origins can access API
- [ ] **Test**: Proper security headers are set

### 9. Deployment Readiness Tests

#### 9.1 Configuration
- [ ] **Test**: Environment variables are properly used
- [ ] **Test**: Production database paths are correct
- [ ] **Test**: Logging configuration is appropriate for production

#### 9.2 Build Process
- [ ] **Test**: Frontend builds without errors
- [ ] **Test**: Production build serves correctly
- [ ] **Test**: Static assets are properly referenced

## Test Execution Checklist

### Pre-Deployment Checklist
- [ ] All database migration tests pass
- [ ] All CRUD operation tests pass
- [ ] Frontend integration tests pass
- [ ] Scheduler functionality tests pass
- [ ] Performance benchmarks meet requirements
- [ ] Error handling behaves correctly
- [ ] Security tests pass
- [ ] Documentation is up to date

### Critical Path Tests (Must Pass)
1. [ ] **Vessel Types CRUD**: Complete save/load cycle works
2. [ ] **Main Data Endpoint**: Returns all data types correctly
3. [ ] **Frontend Loading**: All data editors load and display data
4. [ ] **Data Persistence**: Saves persist across server restarts
5. [ ] **Scheduler Integration**: Basic scheduling works with database data

### Test Automation Scripts

#### Quick API Test Script
```bash
#!/bin/bash
# Save as test_api_quick.sh

echo "Testing OASIS API endpoints..."

# Test main data endpoint
echo "1. Testing main data endpoint..."
curl -f http://localhost:5001/api/data > /dev/null && echo "✓ Main data endpoint OK" || echo "✗ Main data endpoint FAILED"

# Test vessel types
echo "2. Testing vessel types..."
curl -f http://localhost:5001/api/data/vessel_types > /dev/null && echo "✓ Vessel types OK" || echo "✗ Vessel types FAILED"

# Test tanks
echo "3. Testing tanks..."
curl -f http://localhost:5001/api/data/tanks > /dev/null && echo "✓ Tanks OK" || echo "✗ Tanks FAILED"

# Test vessels
echo "4. Testing vessels..."
curl -f http://localhost:5001/api/data/vessels > /dev/null && echo "✓ Vessels OK" || echo "✗ Vessels FAILED"

echo "Quick API test completed."
```

#### Database Integrity Check Script
```bash
#!/bin/bash
# Save as test_db_integrity.sh

echo "Checking database integrity..."

cd backend

# Check if database exists
if [ ! -f "oasis.db" ]; then
    echo "✗ Database file missing"
    exit 1
fi

# Check critical tables
TABLES=("tanks" "vessels" "crudes" "vessel_types" "blending_recipes")
for table in "${TABLES[@]}"; do
    COUNT=$(sqlite3 oasis.db "SELECT COUNT(*) FROM $table")
    if [ $? -eq 0 ]; then
        echo "✓ Table $table exists (rows: $COUNT)"
    else
        echo "✗ Table $table missing or corrupted"
    fi
done

echo "Database integrity check completed."
```

## Test Results Documentation

### Test Result Template
```markdown
## Test Results - [Date]

### Environment
- Backend: Flask [version]
- Frontend: React [version]
- Database: SQLite
- OS: [operating system]

### Test Results Summary
- Total Tests: [number]
- Passed: [number]
- Failed: [number]
- Skipped: [number]

### Critical Issues Found
[List any critical issues that must be fixed before deployment]

### Minor Issues Found
[List any minor issues that can be addressed later]

### Performance Metrics
- Main data endpoint response time: [time]ms
- Frontend load time: [time]ms
- Database query average time: [time]ms

### Recommendation
[Ready for deployment / Needs fixes / Requires further testing]
```

## Conclusion

This comprehensive test plan ensures that all aspects of the OASIS system are thoroughly validated before deployment. Focus on the Critical Path Tests for rapid deployment readiness, then execute the full test suite for complete validation.

**Next Steps:**
1. Execute the Critical Path Tests
2. Fix any issues found
3. Run the complete test suite
4. Document results
5. Proceed with deployment when all tests pass
