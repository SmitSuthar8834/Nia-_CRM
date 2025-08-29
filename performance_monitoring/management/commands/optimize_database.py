"""
Management command for database optimization
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from performance_monitoring.database_optimization import (
    DatabaseOptimizer, TranscriptOptimizer, ConcurrentCallOptimizer
)
from performance_monitoring.cache import PerformanceCache, CacheWarmer


class Command(BaseCommand):
    help = 'Optimize database for performance monitoring and transcript storage'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Analyze current database performance'
        )
        parser.add_argument(
            '--optimize-indexes',
            action='store_true',
            help='Create and optimize database indexes'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old data'
        )
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=30,
            help='Number of days of data to keep (default: 30)'
        )
        parser.add_argument(
            '--optimize-transcripts',
            action='store_true',
            help='Optimize transcript storage'
        )
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Warm up cache with frequently accessed data'
        )
        parser.add_argument(
            '--maintenance-plan',
            action='store_true',
            help='Generate database maintenance plan'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimization tasks'
        )
    
    def handle(self, *args, **options):
        if options['all']:
            options.update({
                'analyze': True,
                'optimize_indexes': True,
                'cleanup': True,
                'optimize_transcripts': True,
                'warm_cache': True
            })
        
        if options['analyze']:
            self.analyze_database()
        
        if options['optimize_indexes']:
            self.optimize_indexes()
        
        if options['cleanup']:
            self.cleanup_old_data(options['cleanup_days'])
        
        if options['optimize_transcripts']:
            self.optimize_transcripts()
        
        if options['warm_cache']:
            self.warm_cache()
        
        if options['maintenance_plan']:
            self.generate_maintenance_plan()
    
    def analyze_database(self):
        """Analyze database performance"""
        self.stdout.write(self.style.SUCCESS('Analyzing database performance...'))
        
        # Analyze table sizes
        table_info = DatabaseOptimizer.analyze_table_sizes()
        
        self.stdout.write('\n=== Table Size Analysis ===')
        for table, info in table_info.items():
            size = info.get('size', 'Unknown')
            self.stdout.write(f'{table}: {size}')
        
        # Analyze query performance
        query_analysis = DatabaseOptimizer.analyze_query_performance()
        
        if query_analysis['index_suggestions']:
            self.stdout.write('\n=== Index Suggestions ===')
            for suggestion in query_analysis['index_suggestions']:
                self.stdout.write(f"Table: {suggestion['table']}")
                self.stdout.write(f"Column: {suggestion['column']}")
                self.stdout.write(f"Size: {suggestion['table_size']}")
                self.stdout.write(f"SQL: {suggestion['suggestion']}")
                self.stdout.write('')
        
        # Analyze transcript storage
        transcript_analysis = TranscriptOptimizer.analyze_transcript_sizes()
        
        self.stdout.write('\n=== Transcript Storage Analysis ===')
        if transcript_analysis.get('total_sessions'):
            self.stdout.write(f"Total sessions with transcripts: {transcript_analysis['total_sessions']}")
            self.stdout.write(f"Average transcript size: {transcript_analysis.get('avg_transcript_size', 0):.0f} bytes")
            self.stdout.write(f"Max transcript size: {transcript_analysis.get('max_transcript_size', 0)} bytes")
            self.stdout.write(f"Total storage used: {transcript_analysis.get('total_transcript_size', 0):,} bytes")
            
            # Platform breakdown
            platform_data = transcript_analysis.get('by_platform', {})
            if platform_data:
                self.stdout.write('\nBy platform:')
                for platform, data in platform_data.items():
                    self.stdout.write(f"  {platform}: {data['count']} sessions, avg size: {data.get('avg_size', 0):.0f} bytes")
        
        # Analyze concurrent call capacity
        capacity_analysis = ConcurrentCallOptimizer.analyze_concurrent_capacity()
        
        self.stdout.write('\n=== Concurrent Call Capacity Analysis ===')
        self.stdout.write(f"Current active calls: {capacity_analysis.get('current_active_calls', 0)}")
        self.stdout.write(f"Peak calls (24h): {capacity_analysis.get('peak_calls_24h', 0)}")
        self.stdout.write(f"Average calls (24h): {capacity_analysis.get('avg_calls_24h', 0):.1f}")
        self.stdout.write(f"Capacity utilization: {capacity_analysis.get('capacity_utilization', 0):.1f}%")
        
        peak_usage = capacity_analysis.get('peak_resource_usage')
        if peak_usage:
            self.stdout.write('\nPeak resource usage:')
            self.stdout.write(f"  CPU: {peak_usage.get('avg_cpu', 0):.1f}%")
            self.stdout.write(f"  Memory: {peak_usage.get('avg_memory', 0):.1f}%")
            self.stdout.write(f"  System load: {peak_usage.get('avg_system_load', 0):.2f}")
    
    def optimize_indexes(self):
        """Optimize database indexes"""
        self.stdout.write(self.style.SUCCESS('Optimizing database indexes...'))
        
        try:
            with transaction.atomic():
                optimizations = DatabaseOptimizer.optimize_performance_metrics_table()
                
                for optimization in optimizations:
                    if 'Failed' in optimization:
                        self.stdout.write(self.style.ERROR(optimization))
                    else:
                        self.stdout.write(self.style.SUCCESS(optimization))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error optimizing indexes: {str(e)}'))
    
    def cleanup_old_data(self, days_to_keep):
        """Clean up old data"""
        self.stdout.write(self.style.SUCCESS(f'Cleaning up data older than {days_to_keep} days...'))
        
        try:
            cleanup_results = DatabaseOptimizer.cleanup_old_metrics(days_to_keep)
            
            self.stdout.write('Cleanup results:')
            for data_type, count in cleanup_results.items():
                self.stdout.write(f'  {data_type}: {count} records deleted')
            
            total_deleted = sum(cleanup_results.values())
            self.stdout.write(self.style.SUCCESS(f'Total records deleted: {total_deleted}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during cleanup: {str(e)}'))
    
    def optimize_transcripts(self):
        """Optimize transcript storage"""
        self.stdout.write(self.style.SUCCESS('Optimizing transcript storage...'))
        
        try:
            # Analyze current transcript storage
            optimizations = DatabaseOptimizer.optimize_transcript_storage()
            
            for optimization in optimizations:
                self.stdout.write(optimization)
            
            # Implement compression for large transcripts
            compression_results = TranscriptOptimizer.implement_transcript_compression()
            
            self.stdout.write('\nTranscript compression results:')
            self.stdout.write(f'  Compressed: {compression_results["compressed"]} transcripts')
            self.stdout.write(f'  Errors: {compression_results["errors"]}')
            self.stdout.write(f'  Space saved: {compression_results["space_saved"]:,} bytes')
            
            # Show archive strategy
            archive_strategies = TranscriptOptimizer.create_transcript_archive_strategy()
            
            self.stdout.write('\nRecommended archive strategies:')
            for strategy in archive_strategies:
                self.stdout.write(f'  {strategy}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error optimizing transcripts: {str(e)}'))
    
    def warm_cache(self):
        """Warm up cache"""
        self.stdout.write(self.style.SUCCESS('Warming up cache...'))
        
        try:
            # Warm performance data
            perf_results = CacheWarmer.warm_performance_data()
            
            self.stdout.write('Performance cache warming results:')
            self.stdout.write(f'  Summaries warmed: {perf_results["summaries_warmed"]}')
            self.stdout.write(f'  Metrics warmed: {perf_results["metrics_warmed"]}')
            
            if perf_results['errors']:
                self.stdout.write('  Errors:')
                for error in perf_results['errors']:
                    self.stdout.write(f'    {error}')
            
            # Warm validation data
            validation_results = CacheWarmer.warm_validation_data()
            
            self.stdout.write('\nValidation cache warming results:')
            self.stdout.write(f'  Sessions warmed: {validation_results["sessions_warmed"]}')
            
            if validation_results['errors']:
                self.stdout.write('  Errors:')
                for error in validation_results['errors']:
                    self.stdout.write(f'    {error}')
            
            # Get cache stats
            cache_stats = PerformanceCache.get_cache_stats()
            
            self.stdout.write('\nCache statistics:')
            for key, value in cache_stats.items():
                self.stdout.write(f'  {key}: {value}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error warming cache: {str(e)}'))
    
    def generate_maintenance_plan(self):
        """Generate database maintenance plan"""
        self.stdout.write(self.style.SUCCESS('Generating database maintenance plan...'))
        
        maintenance_tasks = DatabaseOptimizer.create_database_maintenance_plan()
        
        self.stdout.write('\n=== Database Maintenance Plan ===')
        for task in maintenance_tasks:
            self.stdout.write(task)
        
        # Scaling suggestions
        scaling_suggestions = ConcurrentCallOptimizer.suggest_scaling_optimizations()
        
        self.stdout.write('\n=== Scaling Optimization Suggestions ===')
        for suggestion in scaling_suggestions:
            self.stdout.write(suggestion)
        
        # Load balancing config
        lb_config = ConcurrentCallOptimizer.create_load_balancing_config()
        
        self.stdout.write('\n=== Load Balancing Configuration ===')
        import json
        self.stdout.write(json.dumps(lb_config, indent=2))
        
        self.stdout.write('\n=== Maintenance Schedule Recommendations ===')
        self.stdout.write('Daily:')
        self.stdout.write('  - Run VACUUM ANALYZE on performance tables')
        self.stdout.write('  - Check for long-running queries')
        self.stdout.write('  - Monitor disk space usage')
        
        self.stdout.write('\nWeekly:')
        self.stdout.write('  - Reindex performance-critical indexes')
        self.stdout.write('  - Clean up old performance metrics')
        self.stdout.write('  - Analyze query performance')
        
        self.stdout.write('\nMonthly:')
        self.stdout.write('  - Full vacuum on large tables')
        self.stdout.write('  - Archive old transcripts')
        self.stdout.write('  - Review and optimize slow queries')
        self.stdout.write('  - Update table statistics')
        
        self.stdout.write('\nQuarterly:')
        self.stdout.write('  - Review partitioning strategy')
        self.stdout.write('  - Analyze storage growth trends')
        self.stdout.write('  - Update capacity planning')
        self.stdout.write('  - Review backup and recovery procedures')