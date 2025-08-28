#!/usr/bin/env python
"""
Comprehensive system management script for NIA Meeting Intelligence
"""
import os
import sys
import django
from django.core.management import execute_from_command_line
from django.core.management.base import BaseCommand
from django.utils import timezone
import argparse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meeting_intelligence.settings')
django.setup()


class SystemManager:
    """Comprehensive system management utilities"""
    
    def __init__(self):
        self.commands = {
            'health': self.run_health_check,
            'cleanup': self.run_cleanup,
            'maintenance': self.run_maintenance,
            'backup': self.run_backup,
            'migrate': self.run_migrations,
            'status': self.show_status,
        }
    
    def run_health_check(self, args):
        """Run comprehensive system health check"""
        print("🔍 Running system health check...")
        
        # Run health check command
        execute_from_command_line([
            'manage.py', 'system_health_check',
            '--record-metrics',
            '--alert-threshold', str(args.alert_threshold)
        ])
        
        print("✅ Health check completed")
    
    def run_cleanup(self, args):
        """Run system cleanup operations"""
        print("🧹 Running system cleanup...")
        
        cleanup_commands = [
            ['cleanup_inactive_users', '--days', str(args.days), '--dry-run' if args.dry_run else ''],
            ['cleanup_old_meetings', '--days', str(args.days), '--keep-sales-meetings', '--dry-run' if args.dry_run else ''],
            ['cleanup_old_sessions', '--days', str(args.days), '--keep-completed', '--dry-run' if args.dry_run else ''],
            ['cleanup_sync_logs', '--days', str(args.days), '--keep-errors', '--dry-run' if args.dry_run else ''],
            ['optimize_ai_cache', '--min-hits', '2', '--dry-run' if args.dry_run else ''],
            ['reset_failed_logins', '--hours', '24', '--dry-run' if args.dry_run else ''],
        ]
        
        for cmd in cleanup_commands:
            cmd = [c for c in cmd if c]  # Remove empty strings
            print(f"Running: {' '.join(cmd)}")
            try:
                execute_from_command_line(['manage.py'] + cmd)
            except Exception as e:
                print(f"❌ Error running {cmd[0]}: {e}")
        
        print("✅ System cleanup completed")
    
    def run_maintenance(self, args):
        """Run system maintenance operations"""
        print("🔧 Running system maintenance...")
        
        maintenance_commands = [
            ['migrate_meeting_data', '--operation', 'validate_data'],
            ['collect_analytics'],
            ['generate_reports', '--report-type', 'system_health'],
            ['ai_cache_maintenance'],
        ]
        
        for cmd in maintenance_commands:
            print(f"Running: {' '.join(cmd)}")
            try:
                execute_from_command_line(['manage.py'] + cmd)
            except Exception as e:
                print(f"❌ Error running {cmd[0]}: {e}")
        
        print("✅ System maintenance completed")
    
    def run_backup(self, args):
        """Run system backup operations"""
        print("💾 Running system backup...")
        
        # Database backup
        backup_file = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        try:
            import subprocess
            
            # PostgreSQL backup
            subprocess.run([
                'pg_dump',
                '--host', os.getenv('DB_HOST', 'localhost'),
                '--port', os.getenv('DB_PORT', '5432'),
                '--username', os.getenv('DB_USER', 'postgres'),
                '--dbname', os.getenv('DB_NAME', 'meeting_intelligence'),
                '--file', backup_file,
                '--verbose'
            ], check=True)
            
            print(f"✅ Database backup created: {backup_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Database backup failed: {e}")
        except FileNotFoundError:
            print("❌ pg_dump not found. Please install PostgreSQL client tools.")
    
    def run_migrations(self, args):
        """Run database migrations"""
        print("🔄 Running database migrations...")
        
        try:
            execute_from_command_line(['manage.py', 'migrate'])
            print("✅ Migrations completed")
        except Exception as e:
            print(f"❌ Migration failed: {e}")
    
    def show_status(self, args):
        """Show system status"""
        print("📊 System Status Report")
        print("=" * 50)
        
        try:
            from django.contrib.auth.models import User
            from apps.meetings.models import Meeting
            from apps.debriefings.models import DebriefingSession
            from apps.leads.models import Lead
            from apps.crm_sync.models import CreatioSync
            
            # User statistics
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            print(f"👥 Users: {active_users}/{total_users} active")
            
            # Meeting statistics
            total_meetings = Meeting.objects.count()
            sales_meetings = Meeting.objects.filter(is_sales_meeting=True).count()
            recent_meetings = Meeting.objects.filter(
                start_time__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
            print(f"📅 Meetings: {total_meetings} total, {sales_meetings} sales, {recent_meetings} this week")
            
            # Debriefing statistics
            total_debriefings = DebriefingSession.objects.count()
            completed_debriefings = DebriefingSession.objects.filter(status='completed').count()
            pending_debriefings = DebriefingSession.objects.filter(status='scheduled').count()
            print(f"📝 Debriefings: {completed_debriefings}/{total_debriefings} completed, {pending_debriefings} pending")
            
            # Lead statistics
            total_leads = Lead.objects.count()
            new_leads = Lead.objects.filter(status='new').count()
            print(f"🎯 Leads: {total_leads} total, {new_leads} new")
            
            # CRM sync statistics
            sync_records = CreatioSync.objects.count()
            failed_syncs = CreatioSync.objects.filter(sync_status='failed').count()
            print(f"🔄 CRM Sync: {sync_records} records, {failed_syncs} failed")
            
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ Error getting status: {e}")
    
    def run(self):
        """Main entry point"""
        parser = argparse.ArgumentParser(description='NIA System Management')
        parser.add_argument('command', choices=self.commands.keys(), help='Command to run')
        parser.add_argument('--days', type=int, default=90, help='Days for cleanup operations')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
        parser.add_argument('--alert-threshold', type=float, default=5.0, help='Alert threshold for health checks')
        
        args = parser.parse_args()
        
        print(f"🚀 NIA System Manager - {args.command.upper()}")
        print(f"⏰ Started at: {timezone.now()}")
        print("-" * 50)
        
        try:
            self.commands[args.command](args)
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
        
        print("-" * 50)
        print(f"✅ Completed at: {timezone.now()}")


if __name__ == '__main__':
    manager = SystemManager()
    manager.run()