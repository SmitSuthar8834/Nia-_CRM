"""
Management command to optimize AI cache performance
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.ai_engine.models import AICache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize AI cache by removing expired entries and low-hit entries'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--min-hits',
            type=int,
            default=2,
            help='Minimum hit count to keep cache entries (default: 2)'
        )
        parser.add_argument(
            '--max-age-days',
            type=int,
            default=30,
            help='Maximum age in days for cache entries (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be optimized without actually doing it'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force optimization without confirmation'
        )
    
    def handle(self, *args, **options):
        min_hits = options['min_hits']
        max_age_days = options['max_age_days']
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=max_age_days)
        
        from django.db import models
        
        # Find cache entries to remove
        expired_entries = AICache.objects.filter(expires_at__lt=timezone.now())
        old_entries = AICache.objects.filter(created_at__lt=cutoff_date)
        low_hit_entries = AICache.objects.filter(hit_count__lt=min_hits)
        
        # Combine queries (union)
        entries_to_remove = AICache.objects.filter(
            models.Q(expires_at__lt=timezone.now()) |
            models.Q(created_at__lt=cutoff_date) |
            models.Q(hit_count__lt=min_hits)
        ).distinct()
        
        total_entries = AICache.objects.count()
        entries_to_remove_count = entries_to_remove.count()
        
        self.stdout.write(f'Total cache entries: {total_entries}')
        self.stdout.write(f'Expired entries: {expired_entries.count()}')
        self.stdout.write(f'Old entries (>{max_age_days} days): {old_entries.count()}')
        self.stdout.write(f'Low-hit entries (<{min_hits} hits): {low_hit_entries.count()}')
        self.stdout.write(f'Total entries to remove: {entries_to_remove_count}')
        
        if entries_to_remove_count == 0:
            self.stdout.write(self.style.SUCCESS('No cache entries need optimization'))
            return
        
        # Show cache statistics
        cache_stats = AICache.objects.aggregate(
            avg_hits=models.Avg('hit_count'),
            max_hits=models.Max('hit_count'),
            total_hits=models.Sum('hit_count')
        )
        
        self.stdout.write(f'Cache statistics:')
        self.stdout.write(f'  Average hits per entry: {cache_stats["avg_hits"]:.2f}')
        self.stdout.write(f'  Maximum hits: {cache_stats["max_hits"]}')
        self.stdout.write(f'  Total cache hits: {cache_stats["total_hits"]}')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Confirm action
        if not force:
            percentage = (entries_to_remove_count / total_entries) * 100
            confirm = input(
                f'Remove {entries_to_remove_count} cache entries ({percentage:.1f}% of total)? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform optimization
        try:
            with transaction.atomic():
                deleted_count = entries_to_remove.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully removed {deleted_count} cache entries'
                    )
                )
                
                # Update cache statistics
                remaining_entries = AICache.objects.count()
                space_saved_percentage = ((total_entries - remaining_entries) / total_entries) * 100
                
                self.stdout.write(
                    f'Cache optimization complete: {remaining_entries} entries remaining '
                    f'({space_saved_percentage:.1f}% space saved)'
                )
                
                logger.info(f'AI cache optimization: removed {deleted_count} entries, {remaining_entries} remaining')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during optimization: {str(e)}')
            )
            logger.error(f'Error during AI cache optimization: {str(e)}')