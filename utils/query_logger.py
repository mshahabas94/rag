"""
Query logging and monitoring utilities.
Tracks all queries, performance metrics, and system health.
"""

import os
import logging
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import threading
from collections import defaultdict, deque
import sqlite3
from contextlib import contextmanager
import psutil

from models.schemas import QueryLog, QueryType, SystemStats

logger = logging.getLogger(__name__)

class QueryLogger:
    """Comprehensive query logging and analytics."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # SQLite database for structured logging
        self.db_path = self.log_dir / "query_logs.db"
        self.init_database()
        
        # In-memory stats for quick access
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'sql_queries': 0,
            'rag_queries': 0,
            'hybrid_queries': 0,
            'total_processing_time': 0.0,
            'start_time': time.time()
        }
        
        # Recent queries for monitoring (last 1000)
        self.recent_queries = deque(maxlen=1000)
        self.lock = threading.Lock()
        
        # Performance tracking
        self.performance_metrics = {
            'response_times': deque(maxlen=100),  # Last 100 response times
            'error_rates': defaultdict(int),
            'query_types': defaultdict(int),
            'hourly_stats': defaultdict(lambda: {'count': 0, 'avg_time': 0.0})
        }
    
    def init_database(self):
        """Initialize SQLite database for query logs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        customer_id TEXT,
                        question TEXT NOT NULL,
                        query_type TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        processing_time REAL NOT NULL,
                        sql_query TEXT,
                        row_count INTEGER,
                        error_message TEXT,
                        timestamp DATETIME NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        metadata TEXT
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON query_logs(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_id ON query_logs(customer_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_query_type ON query_logs(query_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_success ON query_logs(success)")
                
                logger.info(f"Query logging database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize query logging database: {e}")
            raise
    
    @contextmanager
    def get_db_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def log_query(self, query_log: QueryLog) -> bool:
        """
        Log a query with all relevant information.
        
        Args:
            query_log: QueryLog object with query details
            
        Returns:
            True if logged successfully
        """
        try:
            with self.lock:
                # Update in-memory stats
                self.stats['total_queries'] += 1
                if query_log.success:
                    self.stats['successful_queries'] += 1
                else:
                    self.stats['failed_queries'] += 1
                
                self.stats['total_processing_time'] += query_log.processing_time
                
                # Update query type stats
                if query_log.query_type == QueryType.SQL:
                    self.stats['sql_queries'] += 1
                elif query_log.query_type == QueryType.RAG:
                    self.stats['rag_queries'] += 1
                elif query_log.query_type == QueryType.HYBRID:
                    self.stats['hybrid_queries'] += 1
                
                # Add to recent queries
                self.recent_queries.append({
                    'timestamp': query_log.timestamp,
                    'question': query_log.question[:100] + "..." if len(query_log.question) > 100 else query_log.question,
                    'query_type': query_log.query_type.value,
                    'success': query_log.success,
                    'processing_time': query_log.processing_time,
                    'customer_id': query_log.customer_id
                })
                
                # Update performance metrics
                self.performance_metrics['response_times'].append(query_log.processing_time)
                self.performance_metrics['query_types'][query_log.query_type.value] += 1
                
                if not query_log.success:
                    error_type = 'unknown'
                    if query_log.error_message:
                        if 'timeout' in query_log.error_message.lower():
                            error_type = 'timeout'
                        elif 'connection' in query_log.error_message.lower():
                            error_type = 'connection'
                        elif 'sql' in query_log.error_message.lower():
                            error_type = 'sql_error'
                        elif 'validation' in query_log.error_message.lower():
                            error_type = 'validation'
                    
                    self.performance_metrics['error_rates'][error_type] += 1
                
                # Hourly stats
                hour_key = query_log.timestamp.strftime('%Y-%m-%d-%H')
                hourly = self.performance_metrics['hourly_stats'][hour_key]
                hourly['count'] += 1
                hourly['avg_time'] = (hourly['avg_time'] * (hourly['count'] - 1) + query_log.processing_time) / hourly['count']
            
            # Store in database
            with self.get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO query_logs (
                        session_id, customer_id, question, query_type, success,
                        processing_time, sql_query, row_count, error_message,
                        timestamp, ip_address, user_agent, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    query_log.session_id,
                    query_log.customer_id,
                    query_log.question,
                    query_log.query_type.value,
                    query_log.success,
                    query_log.processing_time,
                    query_log.sql_query,
                    query_log.row_count,
                    query_log.error_message,
                    query_log.timestamp.isoformat(),
                    query_log.ip_address,
                    query_log.user_agent,
                    json.dumps({}) if not hasattr(query_log, 'metadata') else json.dumps(query_log.metadata or {})
                ))
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
            return False
    
    def get_stats(self) -> SystemStats:
        """Get current system statistics."""
        with self.lock:
            uptime = time.time() - self.stats['start_time']
            avg_processing_time = (
                self.stats['total_processing_time'] / max(1, self.stats['total_queries'])
            )
            
            return SystemStats(
                total_queries=self.stats['total_queries'],
                successful_queries=self.stats['successful_queries'],
                failed_queries=self.stats['failed_queries'],
                avg_processing_time=avg_processing_time,
                sql_queries=self.stats['sql_queries'],
                rag_queries=self.stats['rag_queries'],
                hybrid_queries=self.stats['hybrid_queries'],
                uptime=uptime
            )
    
    def get_recent_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent queries for monitoring."""
        with self.lock:
            recent = list(self.recent_queries)
            return recent[-limit:] if len(recent) > limit else recent
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        with self.lock:
            response_times = list(self.performance_metrics['response_times'])
            
            metrics = {
                'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'p95_response_time': self._percentile(response_times, 95) if response_times else 0,
                'p99_response_time': self._percentile(response_times, 99) if response_times else 0,
                'error_rates': dict(self.performance_metrics['error_rates']),
                'query_type_distribution': dict(self.performance_metrics['query_types']),
                'hourly_stats': dict(self.performance_metrics['hourly_stats'])
            }
            
            return metrics
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list of numbers."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def get_query_history(self, 
                         customer_id: str = None,
                         query_type: str = None,
                         success: bool = None,
                         start_date: datetime = None,
                         end_date: datetime = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get query history with filtering options.
        
        Args:
            customer_id: Filter by customer ID
            query_type: Filter by query type
            success: Filter by success status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            
        Returns:
            List of query records
        """
        try:
            with self.get_db_connection() as conn:
                query = "SELECT * FROM query_logs WHERE 1=1"
                params = []
                
                if customer_id:
                    query += " AND customer_id = ?"
                    params.append(customer_id)
                
                if query_type:
                    query += " AND query_type = ?"
                    params.append(query_type)
                
                if success is not None:
                    query += " AND success = ?"
                    params.append(success)
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get query history: {e}")
            return []
    
    def get_customer_stats(self, customer_id: str) -> Dict[str, Any]:
        """Get statistics for a specific customer."""
        try:
            with self.get_db_connection() as conn:
                # Basic stats
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_queries,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_queries,
                        AVG(processing_time) as avg_processing_time,
                        MIN(timestamp) as first_query,
                        MAX(timestamp) as last_query
                    FROM query_logs 
                    WHERE customer_id = ?
                """, (customer_id,))
                
                basic_stats = dict(cursor.fetchone())
                
                # Query type breakdown
                cursor = conn.execute("""
                    SELECT query_type, COUNT(*) as count
                    FROM query_logs 
                    WHERE customer_id = ?
                    GROUP BY query_type
                """, (customer_id,))
                
                query_types = {row['query_type']: row['count'] for row in cursor.fetchall()}
                
                # Recent activity (last 7 days)
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) as recent_queries
                    FROM query_logs 
                    WHERE customer_id = ? AND timestamp >= ?
                """, (customer_id, week_ago))
                
                recent_activity = cursor.fetchone()['recent_queries']
                
                return {
                    'customer_id': customer_id,
                    'total_queries': basic_stats['total_queries'],
                    'successful_queries': basic_stats['successful_queries'],
                    'failed_queries': basic_stats['total_queries'] - basic_stats['successful_queries'],
                    'success_rate': basic_stats['successful_queries'] / max(1, basic_stats['total_queries']),
                    'avg_processing_time': basic_stats['avg_processing_time'] or 0,
                    'first_query': basic_stats['first_query'],
                    'last_query': basic_stats['last_query'],
                    'query_type_breakdown': query_types,
                    'recent_activity_7d': recent_activity
                }
                
        except Exception as e:
            logger.error(f"Failed to get customer stats for {customer_id}: {e}")
            return {'customer_id': customer_id, 'error': str(e)}
    
    def cleanup_old_logs(self, days_to_keep: int = 90):
        """Clean up old log entries to manage database size."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            with self.get_db_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM query_logs WHERE timestamp < ?",
                    (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old log entries")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    def export_logs(self, 
                   output_file: str,
                   start_date: datetime = None,
                   end_date: datetime = None,
                   format: str = 'json') -> bool:
        """
        Export logs to file.
        
        Args:
            output_file: Output file path
            start_date: Start date for export
            end_date: End date for export
            format: Export format ('json' or 'csv')
            
        Returns:
            True if export successful
        """
        try:
            logs = self.get_query_history(
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Large limit for export
            )
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == 'json':
                with open(output_path, 'w') as f:
                    json.dump(logs, f, indent=2, default=str)
            elif format.lower() == 'csv':
                import csv
                if logs:
                    with open(output_path, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
                        writer.writeheader()
                        writer.writerows(logs)
            
            logger.info(f"Exported {len(logs)} logs to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            return False

class SystemMonitor:
    """Monitor system health and performance."""
    
    def __init__(self):
        self.start_time = time.time()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health information."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Disk usage for logs directory
            disk = psutil.disk_usage('.')
            
            return {
                'uptime_seconds': time.time() - self.start_time,
                'memory': {
                    'total_mb': memory.total / (1024 * 1024),
                    'available_mb': memory.available / (1024 * 1024),
                    'used_mb': memory.used / (1024 * 1024),
                    'percent_used': memory.percent
                },
                'cpu': {
                    'percent_used': cpu_percent,
                    'count': psutil.cpu_count()
                },
                'disk': {
                    'total_gb': disk.total / (1024 * 1024 * 1024),
                    'free_gb': disk.free / (1024 * 1024 * 1024),
                    'used_gb': disk.used / (1024 * 1024 * 1024),
                    'percent_used': (disk.used / disk.total) * 100
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

# Global instances
query_logger = QueryLogger()
system_monitor = SystemMonitor()
