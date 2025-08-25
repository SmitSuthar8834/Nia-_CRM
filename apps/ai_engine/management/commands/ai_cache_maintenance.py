"""
Django management command for AI cache maintenance
Cleans up expired entries, optimizes cache performance, and provides statistics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.ai_engine.models import AICache, AIInteraction
from apps.ai_engine.caching_optimization import get_optimization_service


class Command(BaseCommand):
    help = 'Perform AI cache maintenance and optimization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up expired cache entries',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show cache statistics',
        )
        parser.add_argument(
            '--optimize',
            action='store_true',
            help='Optimize cache performance',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for statistics (default: 7)',
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.cleanup_cache()
        
        if options['stats']:
            self.show_statistics(options['days'])
        
        if options['optimize']:
            self.optimize_cache()
        
        if not any([options['cleanup'], options['stats'], options['optimize']]):
            self.stdout.write("No action specified. Use --help for options.")

    def cleanup_cache(self):
        """Clean up expired and low-performance cache entries"""
        self.stdout.write("Starting cache cleanup...")
        
        # Remove expired entries
        expired_count = AICache.objects.filter(
            expires_at__lte=timezone.now()
        ).count()
        
        AICache.objects.filter(expires_at__lte=timezone.now()).delete()
        
        # Remove low-performance entries older than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        low_perf_count = AICache.objects.filter(
            created_at__lt=cutoff_date,
            hit_count__lt=2
        ).count()
        
        AICache.objects.filter(
            created_at__lt=cutoff_date,
            hit_count__lt=2
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Cache cleanup completed: "
                f"Removed {expired_count} expired entries, "
                f"{low_perf_count} low-performance entries"
            )
        )

    def show_statistics(self, days):
        """Show cache performance statistics"""
        optimization_service = get_optimization_service()
        report = optimization_service.get_optimization_report(days)
        
        self.stdout.write(f"\n=== AI Cache Statistics ({days} days) ===")
        
        usage_metrics = report.get('usage_metrics', {})
        cache_metrics = usage_metrics.get('cache_metrics', {})
        
        self.stdout.write(f"Total interactions: {usage_metrics.get('total_interactions', 0)}")
        self.stdout.write(f"Success rate: {usage_metrics.get('success_rate', 0):.2%}")
        self.stdout.write(f"Cache entries: {cache_metrics.get('total_cache_entries', 0)}")
        self.stdout.write(f"Cache hits: {cache_metrics.get('total_cache_hits', 0)}")
        self.stdout.write(f"Cache hit rate: {cache_metrics.get('estimated_hit_rate', 0):.2%}")
        self.stdout.write(f"API calls saved: {cache_metrics.get('estimated_api_calls_saved', 0)}")
        self.stdout.write(f"Cost savings: ${cache_metrics.get('estimated_cost_savings', 0):.4f}")
        
        # Show optimization suggestions
        suggestions = usage_metrics.get('optimization_suggestions', [])
        if suggestions:
            self.stdout.write("\n=== Optimization Suggestions ===")
            for suggestion in suggestions:
                self.stdout.write(f"• {suggestion}")

    def optimize_cache(self):
        """Optimize cache performance"""
        self.stdout.write("Starting cache optimization...")
        
        optimization_service = get_optimization_service()
        
        # Get current statistics
        report = optimization_service.get_optimization_report(7)
        cache_metrics = report.get('usage_metrics', {}).get('cache_metrics', {})
        
        hit_rate = cache_metrics.get('estimated_hit_rate', 0)
        
        if hit_rate < 0.2:
            self.stdout.write("Low cache hit rate detected. Consider:")
            self.stdout.write("• Increasing cache TTL")
            self.stdout.write("• Enabling semantic caching")
            self.stdout.write("• Reviewing prompt patterns")
        elif hit_rate > 0.8:
            self.stdout.write("Excellent cache performance!")
            self.stdout.write("• Consider extending cache TTL")
            self.stdout.write("• Cache is working optimally")
        else:
            self.stdout.write("Cache performance is acceptable")
        
        self.stdout.write(
            self.style.SUCCESS("Cache optimization analysis completed")
        )