"""
Security utilities for SQL injection prevention and customer data isolation.
Implements comprehensive security measures for database queries.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import time
from collections import defaultdict, deque
import threading
from datetime import datetime, timedelta
import sqlparse
from sqlparse.sql import Statement, Token
from sqlparse.tokens import Keyword, Name

logger = logging.getLogger(__name__)

class SQLSecurityValidator:
    """Validates SQL queries for security threats and compliance."""
    
    # Dangerous SQL keywords that should never appear in generated queries
    FORBIDDEN_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE',
        'EXEC', 'EXECUTE', 'CALL', 'PROCEDURE', 'FUNCTION', 'TRIGGER',
        'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK', 'SAVEPOINT',
        'LOAD', 'OUTFILE', 'INFILE', 'DUMPFILE'
    }
    
    # Suspicious patterns that might indicate injection attempts
    INJECTION_PATTERNS = [
        # r"'.*'.*'",  # Multiple quotes
        r"--.*",     # SQL comments
        r"/\*.*\*/", # Block comments
        r";\s*\w+",  # Multiple statements
        r"\bUNION\s+SELECT\b",  # Union-based injection
        r"\bOR\s+1\s*=\s*1\b",  # Always true conditions
        r"\bAND\s+1\s*=\s*1\b", # Always true conditions
        r"'.*OR.*'", # OR in quotes
        r"'.*AND.*'", # AND in quotes
        r"\bSLEEP\s*\(",  # Time-based attacks
        r"\bBENCHMARK\s*\(",  # Benchmark attacks
        r"\bCONCAT\s*\(",  # Concatenation attacks (sometimes)
        r"0x[0-9a-fA-F]+",  # Hex encoding
        r"CHAR\s*\(",  # Character encoding
        r"ASCII\s*\(",  # ASCII attacks
    ]
    
    # Required security patterns for customer isolation
    REQUIRED_PATTERNS = [
        r"\bcustomer_id\s*=",
        r"\bcustomer_email\s*="
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        self.required_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.REQUIRED_PATTERNS]
    
    def validate_sql(self, sql: str, customer_id: str = None, customer_email: str = None) -> Dict[str, Any]:
        """
        Comprehensive SQL validation for security and compliance.
        
        Args:
            sql: SQL query to validate
            customer_id: Expected customer ID
            customer_email: Expected customer email
            
        Returns:
            Dict with validation results
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'security_score': 1.0,
            'risk_level': 'low'
        }
        
        if not sql or not sql.strip():
            result['valid'] = False
            result['errors'].append("Empty SQL query")
            return result
        
        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()
        
        # 1. Check if it's a SELECT statement
        if not sql_upper.startswith('SELECT'):
            result['valid'] = False
            result['errors'].append("Only SELECT statements are allowed")
            result['security_score'] = 0.0
            result['risk_level'] = 'critical'
        
        # 2. Check for forbidden keywords
        forbidden_found = []
        for keyword in self.FORBIDDEN_KEYWORDS:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                forbidden_found.append(keyword)
        
        if forbidden_found:
            result['valid'] = False
            result['errors'].extend([f"Forbidden keyword: {kw}" for kw in forbidden_found])
            result['security_score'] = 0.0
            result['risk_level'] = 'critical'
        
        # 3. Check for injection patterns
        injection_matches = []
        for pattern in self.compiled_patterns:
            matches = pattern.findall(sql)
            if matches:
                injection_matches.extend(matches)
        
        if injection_matches:
            result['warnings'].extend([f"Suspicious pattern: {match}" for match in injection_matches])
            result['security_score'] *= 0.5
            if result['security_score'] < 0.3:
                result['risk_level'] = 'high'
            elif result['security_score'] < 0.7:
                result['risk_level'] = 'medium'
        
        # 4. Check for customer isolation
        has_customer_filter = any(pattern.search(sql) for pattern in self.required_compiled)
        
        if not has_customer_filter:
            result['valid'] = False
            result['errors'].append("Query must include customer isolation (customer_id or customer_email filter)")
            result['security_score'] *= 0.2
            result['risk_level'] = 'critical'
        
        # 5. Validate customer ID/email in query if provided
        if customer_id:
            if customer_id not in sql:
                result['warnings'].append(f"Expected customer_id '{customer_id}' not found in query")
                result['security_score'] *= 0.8
        
        if customer_email:
            if customer_email not in sql:
                result['warnings'].append(f"Expected customer_email '{customer_email}' not found in query")
                result['security_score'] *= 0.8
        
        # 6. Parse SQL structure for additional validation
        try:
            parsed = sqlparse.parse(sql)
            if parsed:
                structure_result = self._validate_sql_structure(parsed[0])
                result['warnings'].extend(structure_result.get('warnings', []))
                if structure_result.get('errors'):
                    result['errors'].extend(structure_result['errors'])
                    result['valid'] = False
        except Exception as e:
            result['warnings'].append(f"SQL parsing warning: {str(e)}")
        
        # 7. Check query complexity (prevent resource exhaustion)
        complexity_result = self._check_query_complexity(sql)
        if complexity_result['too_complex']:
            result['warnings'].extend(complexity_result['warnings'])
            result['security_score'] *= 0.7
        
        return result
    
    def _validate_sql_structure(self, parsed_sql: Statement) -> Dict[str, Any]:
        """Validate the structure of parsed SQL."""
        result = {'errors': [], 'warnings': []}
        
        # Check for multiple statements
        statements = [token for token in parsed_sql.tokens if isinstance(token, Statement)]
        if len(statements) > 1:
            result['errors'].append("Multiple SQL statements not allowed")
        
        # Look for suspicious token patterns
        for token in parsed_sql.flatten():
            if token.ttype is Keyword:
                keyword = token.value.upper()
                if keyword in self.FORBIDDEN_KEYWORDS:
                    result['errors'].append(f"Forbidden keyword in parsed SQL: {keyword}")
        
        return result
    
    def _check_query_complexity(self, sql: str) -> Dict[str, Any]:
        """Check if query is too complex and might cause performance issues."""
        result = {'too_complex': False, 'warnings': []}
        
        sql_upper = sql.upper()
        
        # Count JOINs
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        if join_count > 5:
            result['warnings'].append(f"Query has {join_count} JOINs, which might be slow")
            result['too_complex'] = True
        
        # Check for nested subqueries
        subquery_count = sql.count('(') - sql.count(')')
        if abs(subquery_count) > 3:
            result['warnings'].append("Query has deeply nested subqueries")
            result['too_complex'] = True
        
        # Check for LIKE with leading wildcards
        if re.search(r"LIKE\s+['\"]%", sql_upper):
            result['warnings'].append("LIKE with leading wildcard can be slow")
        
        # Check query length
        if len(sql) > 2000:
            result['warnings'].append("Query is very long, consider simplifying")
        
        return result
    
    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent injection."""
        if not user_input:
            return ""
        
        # Remove dangerous characters
        sanitized = re.sub(r"[';\"\\]", "", user_input)
        
        # Remove SQL comments
        sanitized = re.sub(r"--.*$", "", sanitized, flags=re.MULTILINE)
        sanitized = re.sub(r"/\*.*?\*/", "", sanitized, flags=re.DOTALL)
        
        # Limit length
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]
        
        return sanitized.strip()

class RateLimiter:
    """Rate limiting for API requests to prevent abuse."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self.lock = threading.Lock()
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed for the given identifier.
        
        Args:
            identifier: Unique identifier (IP, customer_id, etc.)
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Clean old requests
            request_times = self.requests[identifier]
            while request_times and request_times[0] < window_start:
                request_times.popleft()
            
            current_count = len(request_times)
            allowed = current_count < self.max_requests
            
            if allowed:
                request_times.append(now)
            
            return allowed, {
                'current_count': current_count,
                'max_requests': self.max_requests,
                'window_seconds': self.window_seconds,
                'reset_time': window_start + self.window_seconds
            }
    
    def get_stats(self, identifier: str) -> Dict[str, Any]:
        """Get rate limiting stats for identifier."""
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            request_times = self.requests[identifier]
            current_requests = [t for t in request_times if t >= window_start]
            
            return {
                'identifier': identifier,
                'current_requests': len(current_requests),
                'max_requests': self.max_requests,
                'window_seconds': self.window_seconds,
                'requests_remaining': max(0, self.max_requests - len(current_requests)),
                'reset_time': window_start + self.window_seconds
            }

class CustomerIsolationEnforcer:
    """Ensures customer data isolation in all queries."""
    
    @staticmethod
    def add_customer_filter(sql: str, customer_id: str = None, customer_email: str = None) -> str:
        """
        Add customer isolation filter to SQL query.
        
        Args:
            sql: Original SQL query
            customer_id: Customer ID to filter by
            customer_email: Customer email to filter by
            
        Returns:
            Modified SQL with customer filter
        """
        if not customer_id and not customer_email:
            raise ValueError("Either customer_id or customer_email must be provided")
        
        sql_upper = sql.upper()
        
        # Check if customer filter already exists
        if 'CUSTOMER_ID' in sql_upper or 'CUSTOMER_EMAIL' in sql_upper:
            return sql
        
        # Add WHERE clause or extend existing one
        if 'WHERE' in sql_upper:
            # Find the WHERE clause and add AND condition
            where_pos = sql_upper.find('WHERE')
            if customer_id:
                filter_clause = f" AND customer_id = '{customer_id}'"
            else:
                filter_clause = f" AND customer_email = '{customer_email}'"
            
            # Insert after WHERE clause
            insert_pos = sql.find('WHERE', where_pos) + 5  # 5 = len('WHERE')
            
            # Find a good place to insert (after existing conditions)
            remaining = sql[insert_pos:].strip()
            if remaining:
                sql += filter_clause
            else:
                sql = sql[:insert_pos] + f" customer_id = '{customer_id}'" if customer_id else f" customer_email = '{customer_email}'"
        else:
            # Add WHERE clause
            if customer_id:
                sql += f" WHERE customer_id = '{customer_id}'"
            else:
                sql += f" WHERE customer_email = '{customer_email}'"
        
        return sql
    
    @staticmethod
    def validate_customer_access(sql: str, customer_id: str = None, customer_email: str = None) -> bool:
        """
        Validate that SQL query properly isolates customer data.
        
        Args:
            sql: SQL query to validate
            customer_id: Expected customer ID
            customer_email: Expected customer email
            
        Returns:
            True if query properly isolates customer data
        """
        sql_upper = sql.upper()
        
        # Must have customer isolation
        has_customer_id = 'CUSTOMER_ID' in sql_upper
        has_customer_email = 'CUSTOMER_EMAIL' in sql_upper
        
        if not (has_customer_id or has_customer_email):
            return False
        
        # If specific customer provided, must match
        if customer_id and customer_id not in sql:
            return False
        
        if customer_email and customer_email not in sql:
            return False
        
        return True

class SecurityAuditor:
    """Audits security events and maintains security logs."""
    
    def __init__(self):
        self.security_events = deque(maxlen=1000)  # Keep last 1000 events
        self.lock = threading.Lock()
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], severity: str = 'info'):
        """Log a security event."""
        with self.lock:
            event = {
                'timestamp': datetime.now(),
                'event_type': event_type,
                'severity': severity,
                'details': details,
                'event_id': hashlib.md5(f"{time.time()}{event_type}".encode()).hexdigest()[:8]
            }
            
            self.security_events.append(event)
            
            # Log to standard logger based on severity
            log_message = f"Security Event [{event_type}]: {details}"
            if severity == 'critical':
                logger.critical(log_message)
            elif severity == 'high':
                logger.error(log_message)
            elif severity == 'medium':
                logger.warning(log_message)
            else:
                logger.info(log_message)
    
    def get_security_events(self, event_type: str = None, severity: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get security events with optional filtering."""
        with self.lock:
            events = list(self.security_events)
        
        # Filter by event type
        if event_type:
            events = [e for e in events if e['event_type'] == event_type]
        
        # Filter by severity
        if severity:
            events = [e for e in events if e['severity'] == severity]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        return events[:limit]
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get summary of security events."""
        with self.lock:
            events = list(self.security_events)
        
        summary = {
            'total_events': len(events),
            'by_severity': defaultdict(int),
            'by_type': defaultdict(int),
            'recent_critical': 0,
            'last_24h': 0
        }
        
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        
        for event in events:
            summary['by_severity'][event['severity']] += 1
            summary['by_type'][event['event_type']] += 1
            
            if event['timestamp'] > day_ago:
                summary['last_24h'] += 1
                if event['severity'] == 'critical':
                    summary['recent_critical'] += 1
        
        return dict(summary)

# Global instances
sql_validator = SQLSecurityValidator()
rate_limiter = RateLimiter()
customer_enforcer = CustomerIsolationEnforcer()
security_auditor = SecurityAuditor()

# Convenience functions
def validate_sql_security(sql: str, customer_id: str = None, customer_email: str = None) -> Dict[str, Any]:
    """Validate SQL query for security compliance."""
    return sql_validator.validate_sql(sql, customer_id, customer_email)

def enforce_rate_limit(identifier: str) -> Tuple[bool, Dict[str, Any]]:
    """Check rate limit for identifier."""
    return rate_limiter.is_allowed(identifier)

def ensure_customer_isolation(sql: str, customer_id: str = None, customer_email: str = None) -> str:
    """Ensure SQL query has proper customer isolation."""
    return customer_enforcer.add_customer_filter(sql, customer_id, customer_email)

def log_security_event(event_type: str, details: Dict[str, Any], severity: str = 'info'):
    """Log a security event."""
    security_auditor.log_security_event(event_type, details, severity)
