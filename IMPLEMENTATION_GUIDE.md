# OASIS Data Management - Immediate Fix Implementation Guide

## Overview

This document provides step-by-step implementation instructions for addressing the critical vulnerabilities identified in the OASIS JSON data management system. These fixes should be implemented **immediately** before any production deployment.

---

## 🚨 Critical Fix #1: Atomic File Operations

### Problem
Current `json.dump()` calls can be interrupted, leaving corrupted or zero-byte files.

### Solution Implementation

**File**: `/backend/utils/file_operations.py` (NEW FILE)

```python
import json
import os
import tempfile
import fcntl
import shutil
from datetime import datetime
from typing import Any, Dict

class AtomicJSONWriter:
    """Thread-safe atomic JSON file operations with backup support."""
    
    def __init__(self, backup_enabled: bool = True):
        self.backup_enabled = backup_enabled
    
    def write(self, file_path: str, data: Any) -> bool:
        """
        Atomically write JSON data to file with backup creation.
        
        Args:
            file_path: Target file path
            data: Data to write as JSON
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            JSONWriteError: If write operation fails
        """
        try:
            # Create backup if file exists and backup is enabled
            backup_path = None
            if self.backup_enabled and os.path.exists(file_path):
                backup_path = self._create_backup(file_path)
            
            # Write to temporary file first
            temp_path = file_path + '.tmp'
            self._write_temp_file(temp_path, data)
            
            # Atomic rename
            os.rename(temp_path, file_path)
            
            return True
            
        except Exception as e:
            # Cleanup temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            # Restore backup if write failed and backup exists
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, file_path)
                except:
                    pass
            
            raise JSONWriteError(f"Failed to write {file_path}: {str(e)}")
    
    def _write_temp_file(self, temp_path: str, data: Any) -> None:
        """Write data to temporary file with file locking."""
        with open(temp_path, 'w') as f:
            # Lock file for exclusive access
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            
            # Write JSON with proper formatting
            json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Force write to disk
            f.flush()
            os.fsync(f.fileno())
    
    def _create_backup(self, file_path: str) -> str:
        """Create timestamped backup of existing file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{file_path}.backup.{timestamp}"
        shutil.copy2(file_path, backup_path)
        return backup_path

class JSONWriteError(Exception):
    """Custom exception for JSON write operations."""
    pass

# Global writer instance
atomic_writer = AtomicJSONWriter()

def save_json_atomic(file_path: str, data: Any) -> bool:
    """Convenience function for atomic JSON writes."""
    return atomic_writer.write(file_path, data)
```

### Integration Steps

1. **Update api.py save_data() function**:

```python
# Replace existing save_data() function in api.py
from utils.file_operations import save_json_atomic, JSONWriteError

@app.route('/api/save-data', methods=['POST'])
def save_data():
    try:
        data = request.get_json()
        data_type = data.get('type')
        content = data.get('content')
        
        if not data_type or content is None:
            return jsonify({'success': False, 'error': 'Missing type or content'}), 400
        
        # Get file path
        file_path = get_data_file_path(data_type)
        
        # Atomic write with backup
        success = save_json_atomic(file_path, content)
        
        if success:
            # Invalidate cache after successful write
            invalidate_cache(file_path)
            return jsonify({'success': True, 'message': f'{data_type} saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Write operation failed'}), 500
            
    except JSONWriteError as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500
```

---

## 🚨 Critical Fix #2: Cache Invalidation

### Problem
`data_cache` becomes stale when files are modified, leading to inconsistent data views.

### Solution Implementation

**Update api.py**:

```python
import os
from threading import Lock

# Thread-safe cache with invalidation
cache_lock = Lock()
data_cache = {}
cache_timestamps = {}

def get_file_mtime(file_path: str) -> float:
    """Get file modification time."""
    try:
        return os.path.getmtime(file_path)
    except OSError:
        return 0.0

def is_cache_valid(file_path: str) -> bool:
    """Check if cached data is still valid based on file modification time."""
    if file_path not in cache_timestamps:
        return False
    
    current_mtime = get_file_mtime(file_path)
    cached_mtime = cache_timestamps[file_path]
    
    return current_mtime <= cached_mtime

def load_data_file(file_path: str) -> Dict:
    """Load data file with cache invalidation based on file modification time."""
    with cache_lock:
        # Check if we have valid cached data
        if file_path in data_cache and is_cache_valid(file_path):
            return data_cache[file_path]
        
        # Cache miss or invalid - reload from file
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update cache and timestamp
            data_cache[file_path] = data
            cache_timestamps[file_path] = get_file_mtime(file_path)
            
            return data
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Remove invalid cache entries
            data_cache.pop(file_path, None)
            cache_timestamps.pop(file_path, None)
            return {}

def invalidate_cache(file_path: str) -> None:
    """Manually invalidate cache for a specific file."""
    with cache_lock:
        data_cache.pop(file_path, None)
        cache_timestamps.pop(file_path, None)

def clear_all_cache() -> None:
    """Clear entire cache - useful for debugging."""
    with cache_lock:
        data_cache.clear()
        cache_timestamps.clear()
```

---

## 🚨 Critical Fix #3: Enhanced Error Handling

### Problem
Generic error handling provides poor debugging information and no recovery mechanisms.

### Solution Implementation

**File**: `/backend/utils/error_handling.py` (NEW FILE)

```python
import logging
import traceback
from datetime import datetime
from typing import Dict, Any
from enum import Enum

class OperationType(Enum):
    READ = "read"
    WRITE = "write" 
    DELETE = "delete"
    CACHE = "cache"

class DataOperationError(Exception):
    """Base exception for data operations."""
    def __init__(self, operation: OperationType, file_path: str, message: str, original_error: Exception = None):
        self.operation = operation
        self.file_path = file_path
        self.message = message
        self.original_error = original_error
        self.timestamp = datetime.now()
        super().__init__(self.message)

class ErrorHandler:
    """Centralized error handling for data operations."""
    
    def __init__(self):
        self.setup_logging()
    
    def setup_logging(self):
        """Setup structured logging for data operations."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/backend/logs/data_operations.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('DataOperations')
    
    def handle_error(self, operation: OperationType, file_path: str, error: Exception) -> Dict[str, Any]:
        """
        Handle and log data operation errors with context.
        
        Returns:
            Dict containing error details for API response
        """
        error_details = {
            'operation': operation.value,
            'file_path': file_path,
            'error_type': type(error).__name__,
            'message': str(error),
            'timestamp': datetime.now().isoformat()
        }
        
        # Log with full context
        self.logger.error(
            f"Data operation failed: {operation.value} on {file_path}",
            extra={
                'operation': operation.value,
                'file_path': file_path,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'traceback': traceback.format_exc()
            }
        )
        
        # Return sanitized error for API response
        return {
            'success': False,
            'error': self._sanitize_error_message(error),
            'operation': operation.value,
            'details': error_details
        }
    
    def _sanitize_error_message(self, error: Exception) -> str:
        """Sanitize error message for safe client response."""
        if isinstance(error, FileNotFoundError):
            return "Data file not found"
        elif isinstance(error, json.JSONDecodeError):
            return "Invalid data format detected"
        elif isinstance(error, PermissionError):
            return "Insufficient permissions for data operation"
        else:
            return "An unexpected error occurred during data operation"

# Global error handler instance
error_handler = ErrorHandler()
```

**Integration in api.py**:

```python
from utils.error_handling import error_handler, OperationType, DataOperationError

@app.route('/api/save-data', methods=['POST'])
def save_data():
    try:
        data = request.get_json()
        data_type = data.get('type')
        content = data.get('content')
        
        if not data_type or content is None:
            return jsonify({'success': False, 'error': 'Missing type or content'}), 400
        
        file_path = get_data_file_path(data_type)
        
        # Atomic write with enhanced error handling
        success = save_json_atomic(file_path, content)
        
        if success:
            invalidate_cache(file_path)
            return jsonify({'success': True, 'message': f'{data_type} saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Write operation failed'}), 500
            
    except JSONWriteError as e:
        error_response = error_handler.handle_error(OperationType.WRITE, file_path, e)
        return jsonify(error_response), 500
    except Exception as e:
        error_response = error_handler.handle_error(OperationType.WRITE, file_path, e)
        return jsonify(error_response), 500
```

---

## 📋 Implementation Checklist

### Prerequisites
- [ ] Create `/backend/utils/` directory if it doesn't exist
- [ ] Create `/backend/logs/` directory for log files
- [ ] Install required Python packages: `fcntl` (usually built-in on Unix systems)

### Implementation Steps

#### Step 1: Create Utility Files
- [ ] Create `/backend/utils/file_operations.py`
- [ ] Create `/backend/utils/error_handling.py`
- [ ] Add `__init__.py` to make utils a proper package

#### Step 2: Update API Layer
- [ ] Update `save_data()` function in `/backend/api.py`
- [ ] Update `load_data_file()` function in `/backend/api.py`
- [ ] Add imports for new utility modules

#### Step 3: Update All JSON Write Locations
- [ ] Update vessel optimizer in `/backend/scheduler/vessel_optimizer.py`
- [ ] Update scheduler export in `/backend/scheduler/scheduler.py`
- [ ] Update utility functions in `/backend/scheduler/utils.py`

#### Step 4: Testing
- [ ] Test atomic writes with simulated interruption
- [ ] Test cache invalidation with concurrent access
- [ ] Test error handling with various failure scenarios
- [ ] Verify backup creation and restoration

#### Step 5: Monitoring Setup
- [ ] Configure log rotation for data operation logs
- [ ] Set up monitoring for error rates
- [ ] Create alerts for critical data operation failures

---

## 🧪 Testing Procedures

### Test 1: Atomic Write Verification
```python
# Test script to verify atomic writes
import os
import json
import signal
import multiprocessing

def test_atomic_write():
    """Test that writes are truly atomic."""
    test_file = 'test_atomic.json'
    test_data = {'test': 'data', 'large_array': list(range(10000))}
    
    # Simulate interruption during write
    def interrupt_write():
        # Start write in subprocess
        p = multiprocessing.Process(target=save_json_atomic, args=(test_file, test_data))
        p.start()
        
        # Interrupt after short delay
        time.sleep(0.001)  # Very short window
        p.terminate()
        p.join()
        
        # Check file integrity
        if os.path.exists(test_file):
            try:
                with open(test_file, 'r') as f:
                    json.load(f)
                print("✓ File integrity maintained after interruption")
            except json.JSONDecodeError:
                print("✗ File corrupted after interruption")
        else:
            print("✓ No partial file created after interruption")
```

### Test 2: Cache Invalidation Verification
```python
def test_cache_invalidation():
    """Test that cache is properly invalidated."""
    test_file = 'test_cache.json'
    
    # Load file into cache
    data1 = load_data_file(test_file)
    
    # Modify file externally
    with open(test_file, 'w') as f:
        json.dump({'modified': True}, f)
    
    # Load again - should detect change
    data2 = load_data_file(test_file)
    
    if data1 != data2:
        print("✓ Cache invalidation working correctly")
    else:
        print("✗ Cache invalidation failed - stale data returned")
```

---

## 📈 Performance Considerations

### Expected Impact
- **Write Performance**: 10-20% slower due to atomic operations
- **Read Performance**: Minimal impact from cache improvements
- **Memory Usage**: Slight increase from backup files
- **Disk Usage**: Temporary increase from backup files (implement cleanup)

### Optimization Recommendations
1. **Backup Cleanup**: Implement automatic cleanup of old backup files
2. **Cache Size Limits**: Add LRU eviction for large caches  
3. **Compression**: Consider compressing backup files for large datasets
4. **Batch Operations**: Group multiple saves into single atomic operation when possible

---

## 🔄 Rollback Plan

If issues arise after implementation:

1. **Immediate Rollback**:
   - Revert `api.py` to previous version
   - Remove new utility files
   - Restart application

2. **Data Recovery**:
   - Use automatically created backup files
   - Check `/backend/logs/data_operations.log` for operation history
   - Restore from most recent valid backup

3. **Verification**:
   - Test basic save/load operations
   - Verify data integrity
   - Monitor for error rates

---

**Implementation Priority**: CRITICAL - Deploy immediately  
**Estimated Implementation Time**: 4-6 hours  
**Testing Time**: 2-3 hours  
**Total Downtime**: 30 minutes (for deployment)
