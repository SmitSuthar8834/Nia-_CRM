"""
Database optimization utilities for performance monitoring and transcript storage
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.db import connection, transaction
from django.db.models import Count, Avg, Max, Min, Q
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.conf import settings

from .models import PerformanceMetric, CallBotPerformance, AIProcessingPerformance
from meetings.models import CallBotSession, DraftSummary, ValidationSession

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """
    Database optimization utilities for performance monitoring
    """
    
    @staticmethod
    def analyze_table_sizes() -> Dict[str, Dict]:
        """Analyze table sizes and row counts"""
        tables_info = {}
        
        with connection.cursor() as cursor:
            # Get table sizes (PostgreSQL specific)
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        attname,
                        n_distinct,
                        correlation
                    FROM pg_stats 
                    WHERE schemaname = 'public' 
                    AND tablename IN (
                        'performance_monitoring_performancemetric',
                        'performance_monitoring_callbotperformance',
                        'performance_monitoring_aiprocessingperformance',
                        'meetings_callbotsession',
                        'meetings_draftsummary',
                        'meetings_validationsession'
                    )
                    ORDER BY tablename, attname;
                """)
                
                stats = cursor.fetchall()
                for schema, table, column, n_distinct, correlation in stats:
                    if table not in tables_info:
                        tables_info[table] = {'columns': {}}
                    tables_info[table]['columns'][column] = {
                        'n_distinct': n_distinct,
                        'correlation': correlation
                    }
                
                # Get table sizes
                cursor.execute("""
                    SELECT 
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    AND tablename LIKE 'performance_monitoring_%' 
                    OR tablename LIKE 'meetings_%'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
                """)
                
                sizes = cursor.fetchall()
                for table, size_pretty, size_bytes in sizes:
                    if table not in tables_info:
                        tables_info[table] = {}
                    tables_info[table]['size'] = size_pretty
                    tables_info[table]['size_bytes'] = size_bytes
        
        return tables_info
    
    @staticmethod
    def analyze_query_performance() -> Dict[str, List]:
        """Analyze slow queries and suggest optimizations"""
        slow_queries = []
        index_suggestions = []
        
        with connection.cursor() as cursor:
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                # Check for missing indexes on foreign keys
                cursor.execute("""
                    SELECT 
                        t.relname as table_name,
                        a.attname as column_name,
                        pg_size_pretty(pg_relation_size(t.oid)) as table_size
                    FROM pg_class t
                    JOIN pg_attribute a ON a.attrelid = t.oid
                    JOIN pg_type ty ON a.atttypid = ty.oid
                    LEFT JOIN pg_index i ON t.oid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE t.relkind = 'r'
                    AND t.relname LIKE 'performance_monitoring_%'
                    AND a.attname LIKE '%_id'
                    AND i.indrelid IS NULL
                    AND NOT a.attisdropped
                    ORDER BY pg_relation_size(t.oid) DESC;
                """)
                
                missing_indexes = cursor.fetchall()
                for table, column, size in missing_indexes:
                    index_suggestions.append({
                        'table': table,
                        'column': column,
                        'table_size': size,
                        'suggestion': f'CREATE INDEX idx_{table}_{column} ON {table} ({column});'
                    })
        
        return {
            'slow_queries': slow_queries,
            'index_suggestions': index_suggestions
        }
    
    @staticmethod
    def optimize_performance_metrics_table():
        """Optimize the performance metrics table"""
        optimizations = []
        
        with connection.cursor() as cursor:
            # Create composite indexes for common query patterns
            indexes_to_create = [
                {
                    'name': 'idx_perf_metric_type_timestamp_status',
                    'table': 'performance_monitoring_performancemetric',
                    'columns': ['metric_type', 'timestamp', 'status'],
                    'sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_perf_metric_type_timestamp_status 
                        ON performance_monitoring_performancemetric (metric_type, timestamp DESC, status)
                    '''
                },
                {
                    'name': 'idx_perf_metric_name_timestamp',
                    'table': 'performance_monitoring_performancemetric', 
                    'columns': ['metric_name', 'timestamp'],
                    'sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_perf_metric_name_timestamp
                        ON performance_monitoring_performancemetric (metric_name, timestamp DESC)
                    '''
                },
                {
                    'name': 'idx_perf_metric_content_type_object_id',
                    'table': 'performance_monitoring_performancemetric',
                    'columns': ['content_type_id', 'object_id'],
                    'sql': '''
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_perf_metric_content_type_object_id
                        ON performance_monitoring_performancemetric (content_type_id, object_id)
                    '''
                }
            ]
            
            for index_info in indexes_to_create:
                try:
                    cursor.execute(index_info['sql'])
                    optimizations.append(f"Created index: {index_info['name']}")
                except Exception as e:
                    optimizations.append(f"Failed to create {index_info['name']}: {str(e)}")
        
        return optimizations
    
    @staticmethod
    def partition_performance_metrics_by_date():
        """Set up date-based partitioning for performance metrics (PostgreSQL)"""
        if 'postgresql' not in settings.DATABASES['default']['ENGINE']:
            return ["Partitioning only supported on PostgreSQL"]
        
        partitioning_sql = """
        -- Create partitioned table for performance metrics
        CREATE TABLE IF NOT EXISTS performance_monitoring_performancemetric_partitioned (
            LIKE performance_monitoring_performancemetric INCLUDING ALL
        ) PARTITION BY RANGE (timestamp);
        
        -- Create monthly partitions for the next 12 months
        """
        
        partitions = []
        current_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(12):
            partition_date = current_date + timedelta(days=32 * i)
            next_partition_date = current_date + timedelta(days=32 * (i + 1))
            
            partition_name = f"performance_metrics_{partition_date.strftime('%Y_%m')}"
            partition_sql = f"""
            CREATE TABLE IF NOT EXISTS {partition_name} 
            PARTITION OF performance_monitoring_performancemetric_partitioned
            FOR VALUES FROM ('{partition_date.isoformat()}') TO ('{next_partition_date.isoformat()}');
            """
            partitions.append(partition_sql)
        
        return [partitioning_sql] + partitions
    
    @staticmethod
    def cleanup_old_metrics(days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old performance metrics to manage database size"""
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        cleanup_results = {}
        
        # Clean up old performance metrics
        old_metrics = PerformanceMetric.objects.filter(timestamp__lt=cutoff_date)
        metrics_count = old_metrics.count()
        old_metrics.delete()
        cleanup_results['performance_metrics'] = metrics_count
        
        # Clean up old AI processing records
        old_ai_records = AIProcessingPerformance.objects.filter(timestamp__lt=cutoff_date)
        ai_count = old_ai_records.count()
        old_ai_records.delete()
        cleanup_results['ai_processing_records'] = ai_count
        
        # Clean up old call bot performance records (keep longer - 90 days)
        old_callbot_cutoff = timezone.now() - timedelta(days=90)
        old_callbot_records = CallBotPerformance.objects.filter(created_at__lt=old_callbot_cutoff)
        callbot_count = old_callbot_records.count()
        old_callbot_records.delete()
        cleanup_results['call_bot_performance'] = callbot_count
        
        return cleanup_results
    
    @staticmethod
    def optimize_transcript_storage():
        """Optimize transcript storage in call bot sessions"""
        optimizations = []
        
        # Compress large transcripts
        large_transcripts = CallBotSession.objects.filter(
            raw_transcript__isnull=False
        ).extra(
            where=["LENGTH(raw_transcript) > %s"],
            params=[10000]  # Transcripts larger than 10KB
        )
        
        compressed_count = 0
        for session in large_transcripts:
            if session.raw_transcript:
                # In a real implementation, you might use compression
                # For now, we'll just track the optimization opportunity
                compressed_count += 1
        
        optimizations.append(f"Found {compressed_count} transcripts that could be compressed")
        
        # Archive old completed sessions
        archive_cutoff = timezone.now() - timedelta(days=180)  # 6 months
        old_sessions = CallBotSession.objects.filter(
            leave_time__lt=archive_cutoff,
            connection_status='disconnected'
        )
        
        archive_count = old_sessions.count()
        optimizations.append(f"Found {archive_count} old sessions that could be archived")
        
        return optimizations
    
    @staticmethod
    def analyze_validation_session_performance() -> Dict[str, any]:
        """Analyze validation session performance and suggest optimizations"""
        analysis = {}
        
        # Check for long-running validation sessions
        long_running_sessions = ValidationSession.objects.filter(
            validation_status='in_progress',
            started_at__lt=timezone.now() - timedelta(hours=2)
        )
        
        analysis['long_running_sessions'] = long_running_sessions.count()
        
        # Check for expired sessions that haven't been cleaned up
        expired_sessions = ValidationSession.objects.filter(
            expires_at__lt=timezone.now(),
            validation_status__in=['pending', 'in_progress']
        )
        
        analysis['expired_sessions'] = expired_sessions.count()
        
        # Analyze validation completion rates
        total_sessions = ValidationSession.objects.count()
        completed_sessions = ValidationSession.objects.filter(
            validation_status='completed'
        ).count()
        
        analysis['completion_rate'] = (
            completed_sessions / total_sessions * 100 
            if total_sessions > 0 else 0
        )
        
        # Check for sessions with large response data
        large_response_sessions = ValidationSession.objects.extra(
            where=["LENGTH(rep_responses::text) > %s"],
            params=[5000]  # Responses larger than 5KB
        )
        
        analysis['large_response_sessions'] = large_response_sessions.count()
        
        return analysis
    
    @staticmethod
    def create_database_maintenance_plan() -> List[str]:
        """Create a database maintenance plan"""
        maintenance_tasks = [
            "-- Daily maintenance tasks",
            "VACUUM ANALYZE performance_monitoring_performancemetric;",
            "VACUUM ANALYZE performance_monitoring_callbotperformance;",
            "VACUUM ANALYZE performance_monitoring_aiprocessingperformance;",
            "",
            "-- Weekly maintenance tasks", 
            "REINDEX INDEX idx_perf_metric_type_timestamp_status;",
            "REINDEX INDEX idx_perf_metric_name_timestamp;",
            "",
            "-- Monthly maintenance tasks",
            "VACUUM FULL performance_monitoring_performancemetric;",
            "ANALYZE performance_monitoring_performancemetric;",
            "",
            "-- Cleanup tasks (run as needed)",
            f"DELETE FROM performance_monitoring_performancemetric WHERE timestamp < NOW() - INTERVAL '30 days';",
            f"DELETE FROM performance_monitoring_aiprocessingperformance WHERE timestamp < NOW() - INTERVAL '30 days';",
            f"DELETE FROM performance_monitoring_callbotperformance WHERE created_at < NOW() - INTERVAL '90 days';"
        ]
        
        return maintenance_tasks


class TranscriptOptimizer:
    """
    Specialized optimizer for transcript storage and retrieval
    """
    
    @staticmethod
    def analyze_transcript_sizes() -> Dict[str, any]:
        """Analyze transcript sizes and storage patterns"""
        analysis = {}
        
        # Get transcript size statistics
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    AVG(LENGTH(raw_transcript)) as avg_transcript_size,
                    MAX(LENGTH(raw_transcript)) as max_transcript_size,
                    MIN(LENGTH(raw_transcript)) as min_transcript_size,
                    SUM(LENGTH(raw_transcript)) as total_transcript_size
                FROM meetings_callbotsession 
                WHERE raw_transcript IS NOT NULL AND raw_transcript != ''
            """)
            
            result = cursor.fetchone()
            if result:
                analysis['total_sessions'] = result[0]
                analysis['avg_transcript_size'] = result[1]
                analysis['max_transcript_size'] = result[2]
                analysis['min_transcript_size'] = result[3]
                analysis['total_transcript_size'] = result[4]
        
        # Analyze by platform
        platform_analysis = {}
        for platform in ['meet', 'teams', 'zoom']:
            sessions = CallBotSession.objects.filter(platform=platform)
            if sessions.exists():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as count,
                            AVG(LENGTH(raw_transcript)) as avg_size
                        FROM meetings_callbotsession 
                        WHERE platform = %s AND raw_transcript IS NOT NULL
                    """, [platform])
                    
                    result = cursor.fetchone()
                    if result:
                        platform_analysis[platform] = {
                            'count': result[0],
                            'avg_size': result[1]
                        }
        
        analysis['by_platform'] = platform_analysis
        
        return analysis
    
    @staticmethod
    def implement_transcript_compression() -> Dict[str, int]:
        """Implement transcript compression for large transcripts"""
        import gzip
        import base64
        
        results = {'compressed': 0, 'errors': 0, 'space_saved': 0}
        
        # Find large uncompressed transcripts
        large_transcripts = CallBotSession.objects.filter(
            raw_transcript__isnull=False
        ).extra(
            where=["LENGTH(raw_transcript) > %s"],
            params=[5000]  # Compress transcripts larger than 5KB
        )
        
        for session in large_transcripts[:100]:  # Process in batches
            try:
                original_size = len(session.raw_transcript.encode('utf-8'))
                
                # Compress the transcript
                compressed_data = gzip.compress(session.raw_transcript.encode('utf-8'))
                compressed_b64 = base64.b64encode(compressed_data).decode('utf-8')
                
                # Store compressed data (in a real implementation, you'd add a field for this)
                # For now, we'll just calculate the savings
                compressed_size = len(compressed_b64)
                space_saved = original_size - compressed_size
                
                if space_saved > 0:
                    results['compressed'] += 1
                    results['space_saved'] += space_saved
                
            except Exception as e:
                results['errors'] += 1
                logger.error(f"Error compressing transcript for session {session.id}: {str(e)}")
        
        return results
    
    @staticmethod
    def create_transcript_archive_strategy() -> List[str]:
        """Create strategy for archiving old transcripts"""
        strategies = [
            "1. Archive transcripts older than 1 year to cold storage",
            "2. Compress transcripts older than 6 months",
            "3. Keep only summary data for transcripts older than 2 years",
            "4. Implement tiered storage: Hot (0-3 months), Warm (3-12 months), Cold (12+ months)",
            "5. Use external storage (S3, Azure Blob) for archived transcripts",
            "6. Maintain metadata index for archived transcripts",
            "7. Implement on-demand retrieval for archived transcripts"
        ]
        
        return strategies


class ConcurrentCallOptimizer:
    """
    Optimizer for handling concurrent call load
    """
    
    @staticmethod
    def analyze_concurrent_capacity() -> Dict[str, any]:
        """Analyze system capacity for concurrent calls"""
        analysis = {}
        
        # Get current active calls
        active_calls = CallBotSession.objects.filter(
            connection_status__in=['connecting', 'connected', 'transcribing']
        ).count()
        
        analysis['current_active_calls'] = active_calls
        
        # Get peak concurrent calls in last 24 hours
        from .models import ConcurrentCallMetrics
        recent_metrics = ConcurrentCallMetrics.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=24)
        )
        
        if recent_metrics.exists():
            peak_calls = recent_metrics.aggregate(Max('active_calls'))['active_calls__max']
            avg_calls = recent_metrics.aggregate(Avg('active_calls'))['active_calls__avg']
            
            analysis['peak_calls_24h'] = peak_calls
            analysis['avg_calls_24h'] = avg_calls
            analysis['capacity_utilization'] = (peak_calls / 50) * 100 if peak_calls else 0
        
        # Analyze resource usage during peak times
        peak_metrics = recent_metrics.filter(active_calls__gte=30)  # High load threshold
        if peak_metrics.exists():
            analysis['peak_resource_usage'] = {
                'avg_cpu': peak_metrics.aggregate(Avg('avg_cpu_usage'))['avg_cpu_usage__avg'],
                'avg_memory': peak_metrics.aggregate(Avg('avg_memory_usage'))['avg_memory_usage__avg'],
                'avg_system_load': peak_metrics.aggregate(Avg('system_load'))['system_load__avg']
            }
        
        return analysis
    
    @staticmethod
    def suggest_scaling_optimizations() -> List[str]:
        """Suggest optimizations for scaling concurrent calls"""
        suggestions = [
            "1. Implement connection pooling for database connections",
            "2. Use Redis for session state management",
            "3. Implement horizontal scaling with load balancers",
            "4. Optimize AI processing with batch operations",
            "5. Use asynchronous processing for non-critical operations",
            "6. Implement circuit breakers for external API calls",
            "7. Use CDN for static assets and caching",
            "8. Optimize database queries with proper indexing",
            "9. Implement graceful degradation for high load",
            "10. Use monitoring and auto-scaling based on metrics"
        ]
        
        return suggestions
    
    @staticmethod
    def create_load_balancing_config() -> Dict[str, any]:
        """Create load balancing configuration for concurrent calls"""
        config = {
            "load_balancer": {
                "algorithm": "least_connections",
                "health_check": {
                    "endpoint": "/api/performance/monitoring/system-status/",
                    "interval": 30,
                    "timeout": 5,
                    "healthy_threshold": 2,
                    "unhealthy_threshold": 3
                },
                "sticky_sessions": False,
                "max_connections_per_server": 25
            },
            "auto_scaling": {
                "min_instances": 2,
                "max_instances": 10,
                "scale_up_threshold": {
                    "concurrent_calls": 40,
                    "cpu_usage": 70,
                    "memory_usage": 80
                },
                "scale_down_threshold": {
                    "concurrent_calls": 15,
                    "cpu_usage": 30,
                    "memory_usage": 40
                },
                "cooldown_period": 300  # 5 minutes
            },
            "circuit_breaker": {
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "expected_exception_types": [
                    "ConnectionError",
                    "TimeoutError",
                    "APIRateLimitError"
                ]
            }
        }
        
        return config