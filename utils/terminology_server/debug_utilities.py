"""
Debug utilities for NHS Terminology Server operations
Enhanced debugging capabilities for development and troubleshooting
"""

import json
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
from pathlib import Path
import traceback

logger = logging.getLogger(__name__)


@dataclass
class DebugRequest:
    """Debug information for a single request"""
    request_id: str
    endpoint: str
    parameters: Dict[str, Any]
    headers: Dict[str, str]
    timestamp: datetime
    thread_id: str
    snomed_code: Optional[str] = None
    

@dataclass
class DebugResponse:
    """Debug information for a response"""
    request_id: str
    status_code: int
    response_headers: Dict[str, str] 
    response_body: Optional[str]
    response_time: float
    timestamp: datetime
    error_message: Optional[str] = None


@dataclass
class DebugSession:
    """Debug session containing all requests and responses"""
    session_id: str
    started_at: datetime
    requests: List[DebugRequest] = field(default_factory=list)
    responses: List[DebugResponse] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)


class RequestResponseLogger:
    """
    Detailed logging of NHS Terminology Server requests and responses
    """
    
    def __init__(self, debug_mode: bool = False, log_responses: bool = True):
        self.debug_mode = debug_mode
        self.log_responses = log_responses
        self._sessions: Dict[str, DebugSession] = {}
        self._current_session: Optional[str] = None
        self._lock = threading.RLock()
        
        if debug_mode:
            logger.setLevel(logging.DEBUG)
    
    def start_session(self, session_id: str = None) -> str:
        """Start a new debug session"""
        if session_id is None:
            session_id = f"debug_{int(time.time())}"
        
        with self._lock:
            session = DebugSession(
                session_id=session_id,
                started_at=datetime.now()
            )
            self._sessions[session_id] = session
            self._current_session = session_id
            
        if self.debug_mode:
            logger.debug(f"Started debug session: {session_id}")
        
        return session_id
    
    def log_request(self, request: DebugRequest):
        """Log a request"""
        if not self.debug_mode:
            return
            
        with self._lock:
            if self._current_session and self._current_session in self._sessions:
                self._sessions[self._current_session].requests.append(request)
        
        logger.debug(f"Request {request.request_id}: {request.endpoint} with params {request.parameters}")
    
    def log_response(self, response: DebugResponse):
        """Log a response"""
        if not self.debug_mode:
            return
            
        with self._lock:
            if self._current_session and self._current_session in self._sessions:
                self._sessions[self._current_session].responses.append(response)
        
        logger.debug(f"Response {response.request_id}: {response.status_code} in {response.response_time:.3f}s")
        
        if response.error_message:
            logger.error(f"Error in {response.request_id}: {response.error_message}")
    
    def log_error(self, error_message: str):
        """Log an error to current session"""
        if not self.debug_mode:
            return
            
        with self._lock:
            if self._current_session and self._current_session in self._sessions:
                self._sessions[self._current_session].errors.append(error_message)
        
        logger.error(f"Session error: {error_message}")
    
    def end_session(self) -> Optional[DebugSession]:
        """End current debug session and return session data"""
        if not self.debug_mode or not self._current_session:
            return None
            
        with self._lock:
            session = self._sessions.get(self._current_session)
            if session:
                # Calculate statistics
                session.statistics = self._calculate_session_statistics(session)
                logger.debug(f"Ended debug session: {self._current_session}")
            
            self._current_session = None
            return session
    
    def get_session(self, session_id: str) -> Optional[DebugSession]:
        """Get a specific debug session"""
        with self._lock:
            return self._sessions.get(session_id)
    
    def get_current_session(self) -> Optional[DebugSession]:
        """Get current debug session"""
        with self._lock:
            if self._current_session:
                return self._sessions.get(self._current_session)
            return None
    
    def _calculate_session_statistics(self, session: DebugSession) -> Dict[str, Any]:
        """Calculate statistics for a debug session"""
        stats = {
            'total_requests': len(session.requests),
            'total_responses': len(session.responses),
            'total_errors': len(session.errors),
            'average_response_time': 0.0,
            'min_response_time': 0.0,
            'max_response_time': 0.0,
            'success_rate': 0.0,
            'endpoints_used': set(),
            'status_codes': {},
            'error_types': {}
        }
        
        if session.responses:
            response_times = [r.response_time for r in session.responses]
            stats['average_response_time'] = sum(response_times) / len(response_times)
            stats['min_response_time'] = min(response_times)
            stats['max_response_time'] = max(response_times)
            
            successful_responses = len([r for r in session.responses if 200 <= r.status_code < 300])
            stats['success_rate'] = (successful_responses / len(session.responses)) * 100
            
            # Status code distribution
            for response in session.responses:
                code = str(response.status_code)
                stats['status_codes'][code] = stats['status_codes'].get(code, 0) + 1
        
        if session.requests:
            stats['endpoints_used'] = set(r.endpoint for r in session.requests)
        
        return stats
    
    def export_session(self, session_id: str, file_path: str) -> bool:
        """Export debug session to file"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        try:
            export_data = {
                'session_id': session.session_id,
                'started_at': session.started_at.isoformat(),
                'statistics': session.statistics,
                'requests': [
                    {
                        'request_id': r.request_id,
                        'endpoint': r.endpoint,
                        'parameters': r.parameters,
                        'headers': dict(r.headers),
                        'timestamp': r.timestamp.isoformat(),
                        'thread_id': r.thread_id,
                        'snomed_code': r.snomed_code
                    }
                    for r in session.requests
                ],
                'responses': [
                    {
                        'request_id': r.request_id,
                        'status_code': r.status_code,
                        'response_headers': dict(r.response_headers),
                        'response_body': r.response_body if self.log_responses else '[REDACTED]',
                        'response_time': r.response_time,
                        'timestamp': r.timestamp.isoformat(),
                        'error_message': r.error_message
                    }
                    for r in session.responses
                ],
                'errors': session.errors
            }
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Debug session {session_id} exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export debug session: {str(e)}")
            return False


class PerformanceProfiler:
    """
    Performance profiler for NHS Terminology Server operations
    """
    
    def __init__(self):
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def start_profile(self, profile_name: str) -> str:
        """Start performance profiling"""
        profile_id = f"{profile_name}_{int(time.time())}"
        
        with self._lock:
            self._profiles[profile_id] = {
                'name': profile_name,
                'started_at': time.time(),
                'checkpoints': [],
                'memory_samples': [],
                'operations': []
            }
        
        logger.debug(f"Started performance profile: {profile_id}")
        return profile_id
    
    def checkpoint(self, profile_id: str, checkpoint_name: str, data: Dict[str, Any] = None):
        """Add a checkpoint to the profile"""
        with self._lock:
            if profile_id in self._profiles:
                checkpoint = {
                    'name': checkpoint_name,
                    'timestamp': time.time(),
                    'data': data or {}
                }
                self._profiles[profile_id]['checkpoints'].append(checkpoint)
                
                logger.debug(f"Profile {profile_id} checkpoint: {checkpoint_name}")
    
    def record_operation(self, profile_id: str, operation_name: str, 
                        duration: float, success: bool, details: Dict[str, Any] = None):
        """Record an operation in the profile"""
        with self._lock:
            if profile_id in self._profiles:
                operation = {
                    'name': operation_name,
                    'duration': duration,
                    'success': success,
                    'timestamp': time.time(),
                    'details': details or {}
                }
                self._profiles[profile_id]['operations'].append(operation)
    
    def end_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """End profiling and return results"""
        with self._lock:
            if profile_id not in self._profiles:
                return None
            
            profile = self._profiles[profile_id]
            end_time = time.time()
            total_time = end_time - profile['started_at']
            
            # Calculate summary statistics
            operations = profile['operations']
            summary = {
                'profile_name': profile['name'],
                'total_time': total_time,
                'total_operations': len(operations),
                'successful_operations': len([op for op in operations if op['success']]),
                'failed_operations': len([op for op in operations if not op['success']]),
                'average_operation_time': 0.0,
                'checkpoints': profile['checkpoints'],
                'operations': operations
            }
            
            if operations:
                op_times = [op['duration'] for op in operations]
                summary['average_operation_time'] = sum(op_times) / len(op_times)
                summary['min_operation_time'] = min(op_times)
                summary['max_operation_time'] = max(op_times)
                
                # Operation type breakdown
                op_types = {}
                for op in operations:
                    op_name = op['name']
                    if op_name not in op_types:
                        op_types[op_name] = {'count': 0, 'total_time': 0, 'success_count': 0}
                    
                    op_types[op_name]['count'] += 1
                    op_types[op_name]['total_time'] += op['duration']
                    if op['success']:
                        op_types[op_name]['success_count'] += 1
                
                summary['operation_breakdown'] = op_types
            
            del self._profiles[profile_id]
            logger.info(f"Performance profile {profile_id} completed in {total_time:.3f}s")
            
            return summary


class DebugContextManager:
    """
    Context manager for automatic debug session management
    """
    
    def __init__(self, logger: RequestResponseLogger, profiler: PerformanceProfiler,
                 session_name: str = None, profile_name: str = None):
        self.logger = logger
        self.profiler = profiler
        self.session_name = session_name or f"context_{int(time.time())}"
        self.profile_name = profile_name or f"profile_{int(time.time())}"
        self.session_id: Optional[str] = None
        self.profile_id: Optional[str] = None
    
    def __enter__(self):
        self.session_id = self.logger.start_session(self.session_name)
        self.profile_id = self.profiler.start_profile(self.profile_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_msg = f"Exception in debug context: {exc_type.__name__}: {exc_val}"
            self.logger.log_error(error_msg)
        
        session = self.logger.end_session()
        profile = self.profiler.end_profile(self.profile_id) if self.profile_id else None
        
        return False  # Don't suppress exceptions
    
    def checkpoint(self, name: str, data: Dict[str, Any] = None):
        """Add a checkpoint during the debug context"""
        if self.profile_id:
            self.profiler.checkpoint(self.profile_id, name, data)
    
    def record_operation(self, name: str, duration: float, success: bool, details: Dict[str, Any] = None):
        """Record an operation during the debug context"""
        if self.profile_id:
            self.profiler.record_operation(self.profile_id, name, duration, success, details)


# Global debug instances
_debug_logger = RequestResponseLogger()
_debug_profiler = PerformanceProfiler()


def get_debug_logger() -> RequestResponseLogger:
    """Get the global debug logger"""
    return _debug_logger


def get_debug_profiler() -> PerformanceProfiler:
    """Get the global debug profiler"""
    return _debug_profiler


def enable_debug_mode():
    """Enable debug mode globally"""
    global _debug_logger
    _debug_logger.debug_mode = True
    logger.setLevel(logging.DEBUG)


def disable_debug_mode():
    """Disable debug mode globally"""
    global _debug_logger
    _debug_logger.debug_mode = False


def create_debug_context(session_name: str = None, profile_name: str = None) -> DebugContextManager:
    """Create a debug context manager"""
    return DebugContextManager(_debug_logger, _debug_profiler, session_name, profile_name)


def format_debug_summary(session: DebugSession, profile_summary: Dict[str, Any] = None) -> str:
    """Format debug information into a readable summary"""
    summary = [
        f"Debug Session: {session.session_id}",
        f"Started: {session.started_at}",
        f"Requests: {len(session.requests)}",
        f"Responses: {len(session.responses)}",
        f"Errors: {len(session.errors)}"
    ]
    
    if session.statistics:
        stats = session.statistics
        summary.extend([
            f"Success Rate: {stats.get('success_rate', 0):.1f}%",
            f"Average Response Time: {stats.get('average_response_time', 0):.3f}s",
            f"Endpoints Used: {len(stats.get('endpoints_used', []))}"
        ])
    
    if profile_summary:
        summary.extend([
            "",
            f"Performance Profile:",
            f"Total Time: {profile_summary.get('total_time', 0):.3f}s",
            f"Operations: {profile_summary.get('total_operations', 0)}",
            f"Average Operation Time: {profile_summary.get('average_operation_time', 0):.3f}s"
        ])
    
    return "\n".join(summary)