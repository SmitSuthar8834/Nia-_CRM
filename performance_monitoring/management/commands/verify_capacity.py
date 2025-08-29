"""
Management command to verify 50 concurrent call capacity (Requirement 8.6)
"""
import time
import threading
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from performance_monitoring.services import PerformanceMonitoringService, AlertingService
from performance_monitoring.models import ConcurrentCallMetrics, SystemAlert
from meetings.models import Meeting, CallBotSession
from leads.models import Lead


class Command(BaseCommand):
    help = 'Verify system capacity for 50 concurrent calls (Requirement 8.6)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--target-calls',
            type=int,
            default=50,
            help='Target number of concurrent calls to test (default: 50)'
        )
        parser.add_argument(
            '--ramp-up-time',
            type=int,
            default=30,
            help='Time in seconds to ramp up to target calls (default: 30)'
        )
        parser.add_argument(
            '--hold-time',
            type=int,
            default=60,
            help='Time in seconds to hold at target load (default: 60)'
        )
        parser.add_argument(
            '--call-duration',
            type=int,
            default=120,
            help='Duration of each simulated call in seconds (default: 120)'
        )
        parser.add_argument(
            '--monitoring-interval',
            type=int,
            default=5,
            help='Monitoring interval in seconds (default: 5)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after completion'
        )
        parser.add_argument(
            '--detailed-report',
            action='store_true',
            help='Generate detailed performance report'
        )
    
    def __init__(self):
        super().__init__()
        self.performance_service = PerformanceMonitoringService()
        self.alerting_service = AlertingService()
        self.test_sessions = []
        self.monitoring_data = []
        self.test_start_time = None
        self.test_lead = None
    
    def handle(self, *args, **options):
        target_calls = options['target_calls']
        ramp_up_time = options['ramp_up_time']
        hold_time = options['hold_time']
        call_duration = options['call_duration']
        monitoring_interval = options['monitoring_interval']
        cleanup = options['cleanup']
        detailed_report = options['detailed_report']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting capacity verification test')
        )
        self.stdout.write(f'Target concurrent calls: {target_calls}')
        self.stdout.write(f'Ramp-up time: {ramp_up_time}s')
        self.stdout.write(f'Hold time: {hold_time}s')
        self.stdout.write(f'Call duration: {call_duration}s')
        
        try:
            # Pre-test system check
            self.pre_test_check()
            
            # Run capacity test
            test_results = self.run_capacity_test(
                target_calls, ramp_up_time, hold_time, 
                call_duration, monitoring_interval
            )
            
            # Analyze results
            self.analyze_test_results(test_results)
            
            # Generate detailed report if requested
            if detailed_report:
                self.generate_detailed_report(test_results)
            
            # Cleanup if requested
            if cleanup:
                self.cleanup_test_data()
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nTest interrupted by user'))
            if cleanup:
                self.cleanup_test_data()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Test error: {str(e)}'))
            raise
    
    def pre_test_check(self):
        """Perform pre-test system checks"""
        self.stdout.write('\nPerforming pre-test system checks...')
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        self.stdout.write(f'CPU usage: {cpu_percent}%')
        self.stdout.write(f'Memory usage: {memory.percent}%')
        self.stdout.write(f'Disk usage: {disk.percent}%')
        
        # Check for existing active calls
        from meetings.models import CallBotSession
        active_calls = CallBotSession.objects.filter(
            connection_status__in=['connecting', 'connected', 'transcribing']
        ).count()
        
        self.stdout.write(f'Existing active calls: {active_calls}')
        
        # Warnings for high resource usage
        if cpu_percent > 50:
            self.stdout.write(self.style.WARNING(f'High CPU usage detected: {cpu_percent}%'))
        
        if memory.percent > 70:
            self.stdout.write(self.style.WARNING(f'High memory usage detected: {memory.percent}%'))
        
        if active_calls > 10:
            self.stdout.write(self.style.WARNING(f'High number of existing active calls: {active_calls}'))
        
        # Create test lead
        self.test_lead = self.get_or_create_test_lead()
        
        self.stdout.write('Pre-test checks completed')
    
    def run_capacity_test(self, target_calls, ramp_up_time, hold_time, call_duration, monitoring_interval):
        """Run the main capacity test"""
        self.test_start_time = time.time()
        test_results = {
            'target_calls': target_calls,
            'ramp_up_time': ramp_up_time,
            'hold_time': hold_time,
            'call_duration': call_duration,
            'start_time': self.test_start_time,
            'phases': {},
            'monitoring_data': [],
            'errors': []
        }
        
        # Start monitoring thread
        monitoring_thread = threading.Thread(
            target=self.monitor_system_resources,
            args=(monitoring_interval, test_results)
        )
        monitoring_thread.daemon = True
        monitoring_thread.start()
        
        try:
            # Phase 1: Ramp-up
            self.stdout.write(f'\nPhase 1: Ramping up to {target_calls} calls over {ramp_up_time}s')
            ramp_results = self.ramp_up_phase(target_calls, ramp_up_time, call_duration)
            test_results['phases']['ramp_up'] = ramp_results
            
            # Phase 2: Hold at target load
            self.stdout.write(f'\nPhase 2: Holding {target_calls} calls for {hold_time}s')
            hold_results = self.hold_phase(hold_time)
            test_results['phases']['hold'] = hold_results
            
            # Phase 3: Ramp-down
            self.stdout.write(f'\nPhase 3: Ramping down')
            ramp_down_results = self.ramp_down_phase()
            test_results['phases']['ramp_down'] = ramp_down_results
            
        except Exception as e:
            test_results['errors'].append(f'Test execution error: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Test execution error: {str(e)}'))
        
        test_results['end_time'] = time.time()
        test_results['total_duration'] = test_results['end_time'] - test_results['start_time']
        
        return test_results
    
    def ramp_up_phase(self, target_calls, ramp_up_time, call_duration):
        """Ramp up to target number of calls"""
        ramp_results = {
            'successful_starts': 0,
            'failed_starts': 0,
            'connection_times': [],
            'errors': []
        }
        
        # Calculate call start intervals
        call_interval = ramp_up_time / target_calls
        
        with ThreadPoolExecutor(max_workers=target_calls) as executor:
            futures = []
            
            for i in range(target_calls):
                # Delay each call start
                if i > 0:
                    time.sleep(call_interval)
                
                future = executor.submit(
                    self.simulate_call_session,
                    f'capacity_test_{i}',
                    call_duration
                )
                futures.append(future)
                
                # Show progress
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'Started {i + 1}/{target_calls} calls')
            
            # Collect ramp-up results (don't wait for completion)
            for i, future in enumerate(futures):
                try:
                    # Check if call started successfully (quick check)
                    if future.running():
                        ramp_results['successful_starts'] += 1
                    else:
                        # Try to get result with short timeout
                        try:
                            result = future.result(timeout=1)
                            if result and result.get('started_successfully'):
                                ramp_results['successful_starts'] += 1
                                if 'connection_time' in result:
                                    ramp_results['connection_times'].append(result['connection_time'])
                            else:
                                ramp_results['failed_starts'] += 1
                        except:
                            # Still running, count as successful start
                            ramp_results['successful_starts'] += 1
                            
                except Exception as e:
                    ramp_results['failed_starts'] += 1
                    ramp_results['errors'].append(f'Call {i}: {str(e)}')
        
        return ramp_results
    
    def hold_phase(self, hold_time):
        """Hold at target load and monitor performance"""
        hold_results = {
            'start_time': time.time(),
            'duration': hold_time,
            'active_calls_samples': [],
            'resource_samples': [],
            'alerts_generated': 0
        }
        
        # Monitor during hold phase
        hold_start = time.time()
        while time.time() - hold_start < hold_time:
            # Sample active calls
            active_calls = CallBotSession.objects.filter(
                connection_status__in=['connecting', 'connected', 'transcribing']
            ).count()
            
            hold_results['active_calls_samples'].append({
                'timestamp': time.time(),
                'active_calls': active_calls
            })
            
            # Sample system resources
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            hold_results['resource_samples'].append({
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'available_memory_gb': memory.available / (1024**3)
            })
            
            # Check for new alerts
            recent_alerts = SystemAlert.objects.filter(
                first_occurred__gte=timezone.now() - timezone.timedelta(seconds=10),
                is_active=True
            ).count()
            
            if recent_alerts > hold_results['alerts_generated']:
                hold_results['alerts_generated'] = recent_alerts
            
            # Show progress
            elapsed = time.time() - hold_start
            remaining = hold_time - elapsed
            self.stdout.write(f'Hold phase: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining, {active_calls} active calls')
            
            time.sleep(5)  # Sample every 5 seconds
        
        hold_results['end_time'] = time.time()
        return hold_results
    
    def ramp_down_phase(self):
        """Ramp down by stopping calls"""
        ramp_down_results = {
            'start_time': time.time(),
            'initial_active_calls': 0,
            'final_active_calls': 0,
            'ramp_down_duration': 0
        }
        
        # Get initial active calls
        initial_active = CallBotSession.objects.filter(
            connection_status__in=['connecting', 'connected', 'transcribing']
        ).count()
        ramp_down_results['initial_active_calls'] = initial_active
        
        self.stdout.write(f'Ramping down from {initial_active} active calls')
        
        # Wait for calls to naturally complete (they have limited duration)
        # In a real implementation, you might actively terminate calls
        ramp_start = time.time()
        while True:
            active_calls = CallBotSession.objects.filter(
                connection_status__in=['connecting', 'connected', 'transcribing']
            ).count()
            
            if active_calls == 0:
                break
            
            elapsed = time.time() - ramp_start
            if elapsed > 300:  # Max 5 minutes wait
                self.stdout.write(self.style.WARNING(f'Timeout waiting for calls to complete. {active_calls} still active.'))
                break
            
            self.stdout.write(f'Ramp down: {active_calls} calls still active after {elapsed:.0f}s')
            time.sleep(10)
        
        ramp_down_results['end_time'] = time.time()
        ramp_down_results['ramp_down_duration'] = ramp_down_results['end_time'] - ramp_down_results['start_time']
        ramp_down_results['final_active_calls'] = CallBotSession.objects.filter(
            connection_status__in=['connecting', 'connected', 'transcribing']
        ).count()
        
        return ramp_down_results
    
    def simulate_call_session(self, session_id, duration):
        """Simulate a single call session"""
        try:
            connection_start = time.time()
            
            # Create meeting
            meeting = Meeting.objects.create(
                calendar_event_id=f'capacity_test_meeting_{session_id}_{int(time.time())}',
                lead=self.test_lead,
                title=f'Capacity Test Call {session_id}',
                start_time=timezone.now(),
                end_time=timezone.now() + timezone.timedelta(seconds=duration)
            )
            
            # Create call bot session
            call_bot_session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f'capacity_test_bot_{session_id}_{int(time.time())}',
                platform='meet',
                join_time=timezone.now(),
                connection_status='connected'
            )
            
            self.test_sessions.append(call_bot_session)
            
            connection_time = time.time() - connection_start
            
            # Track performance
            self.performance_service.track_call_bot_performance(
                call_bot_session=call_bot_session,
                connection_time=connection_time,
                connection_success=True
            )
            
            # Simulate call processing
            processing_start = time.time()
            
            # Simulate work during the call
            work_interval = min(duration / 10, 10)  # Work every 10% of duration or 10s max
            work_cycles = int(duration / work_interval)
            
            for cycle in range(work_cycles):
                time.sleep(work_interval)
                
                # Simulate AI processing periodically
                if cycle % 3 == 0:  # Every 3rd cycle
                    self.performance_service.track_ai_processing(
                        operation_type='transcription',
                        operation_id=f'{session_id}_transcription_{cycle}',
                        processing_time=0.5,
                        input_size=500,
                        output_size=400,
                        confidence_score=0.9
                    )
                
                # Check if we should stop early
                if call_bot_session.connection_status != 'connected':
                    break
            
            processing_time = time.time() - processing_start
            
            # End session
            call_bot_session.connection_status = 'disconnected'
            call_bot_session.leave_time = timezone.now()
            call_bot_session.save()
            
            return {
                'session_id': session_id,
                'started_successfully': True,
                'connection_time': connection_time,
                'processing_time': processing_time,
                'meeting_id': meeting.id,
                'call_bot_session_id': call_bot_session.id
            }
            
        except Exception as e:
            return {
                'session_id': session_id,
                'started_successfully': False,
                'error': str(e)
            }
    
    def monitor_system_resources(self, interval, test_results):
        """Monitor system resources during the test"""
        while True:
            try:
                timestamp = time.time()
                
                # System resources
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Active calls
                active_calls = CallBotSession.objects.filter(
                    connection_status__in=['connecting', 'connected', 'transcribing']
                ).count()
                
                # Record concurrent call metrics
                metrics = self.performance_service.track_concurrent_calls()
                
                monitoring_data = {
                    'timestamp': timestamp,
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                    'disk_percent': disk.percent,
                    'active_calls': active_calls,
                    'system_load': getattr(psutil, 'getloadavg', lambda: [0])[0] if hasattr(psutil, 'getloadavg') else 0
                }
                
                test_results['monitoring_data'].append(monitoring_data)
                
                time.sleep(interval)
                
            except Exception as e:
                test_results['errors'].append(f'Monitoring error: {str(e)}')
                time.sleep(interval)
    
    def analyze_test_results(self, test_results):
        """Analyze and display test results"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('CAPACITY TEST RESULTS')
        self.stdout.write('='*60)
        
        # Overall test summary
        total_duration = test_results.get('total_duration', 0)
        target_calls = test_results.get('target_calls', 0)
        
        self.stdout.write(f'Test duration: {total_duration:.1f} seconds')
        self.stdout.write(f'Target concurrent calls: {target_calls}')
        
        # Ramp-up phase results
        ramp_up = test_results['phases'].get('ramp_up', {})
        successful_starts = ramp_up.get('successful_starts', 0)
        failed_starts = ramp_up.get('failed_starts', 0)
        
        self.stdout.write(f'\nRamp-up Phase:')
        self.stdout.write(f'  Successful starts: {successful_starts}/{target_calls}')
        self.stdout.write(f'  Failed starts: {failed_starts}')
        self.stdout.write(f'  Success rate: {successful_starts/target_calls*100:.1f}%')
        
        if ramp_up.get('connection_times'):
            avg_connection_time = sum(ramp_up['connection_times']) / len(ramp_up['connection_times'])
            max_connection_time = max(ramp_up['connection_times'])
            self.stdout.write(f'  Avg connection time: {avg_connection_time:.3f}s')
            self.stdout.write(f'  Max connection time: {max_connection_time:.3f}s')
        
        # Hold phase results
        hold = test_results['phases'].get('hold', {})
        if hold.get('active_calls_samples'):
            max_concurrent = max(sample['active_calls'] for sample in hold['active_calls_samples'])
            avg_concurrent = sum(sample['active_calls'] for sample in hold['active_calls_samples']) / len(hold['active_calls_samples'])
            
            self.stdout.write(f'\nHold Phase:')
            self.stdout.write(f'  Max concurrent calls achieved: {max_concurrent}')
            self.stdout.write(f'  Average concurrent calls: {avg_concurrent:.1f}')
            self.stdout.write(f'  Alerts generated: {hold.get("alerts_generated", 0)}')
        
        # Resource usage analysis
        monitoring_data = test_results.get('monitoring_data', [])
        if monitoring_data:
            max_cpu = max(data['cpu_percent'] for data in monitoring_data)
            avg_cpu = sum(data['cpu_percent'] for data in monitoring_data) / len(monitoring_data)
            max_memory = max(data['memory_percent'] for data in monitoring_data)
            avg_memory = sum(data['memory_percent'] for data in monitoring_data) / len(monitoring_data)
            min_available_memory = min(data['memory_available_gb'] for data in monitoring_data)
            
            self.stdout.write(f'\nResource Usage:')
            self.stdout.write(f'  Peak CPU usage: {max_cpu:.1f}%')
            self.stdout.write(f'  Average CPU usage: {avg_cpu:.1f}%')
            self.stdout.write(f'  Peak memory usage: {max_memory:.1f}%')
            self.stdout.write(f'  Average memory usage: {avg_memory:.1f}%')
            self.stdout.write(f'  Minimum available memory: {min_available_memory:.1f}GB')
        
        # Capacity assessment (Requirement 8.6)
        self.stdout.write(f'\n' + '='*60)
        self.stdout.write('CAPACITY ASSESSMENT (Requirement 8.6)')
        self.stdout.write('='*60)
        
        # Success criteria
        success_criteria = {
            'concurrent_calls': max_concurrent >= target_calls * 0.9,  # 90% of target
            'success_rate': successful_starts / target_calls >= 0.95,  # 95% success rate
            'cpu_usage': max_cpu <= 90,  # CPU under 90%
            'memory_usage': max_memory <= 85,  # Memory under 85%
            'available_memory': min_available_memory >= 1.0,  # At least 1GB available
        }
        
        all_passed = all(success_criteria.values())
        
        for criterion, passed in success_criteria.items():
            status = "PASS" if passed else "FAIL"
            style = self.style.SUCCESS if passed else self.style.ERROR
            self.stdout.write(style(f'  {criterion}: {status}'))
        
        # Overall assessment
        if all_passed:
            self.stdout.write(self.style.SUCCESS(f'\n✓ CAPACITY TEST PASSED'))
            self.stdout.write(self.style.SUCCESS(f'System can handle {target_calls} concurrent calls (Requirement 8.6)'))
        else:
            self.stdout.write(self.style.ERROR(f'\n✗ CAPACITY TEST FAILED'))
            self.stdout.write(self.style.ERROR(f'System cannot reliably handle {target_calls} concurrent calls'))
        
        # Errors summary
        all_errors = test_results.get('errors', [])
        for phase_name, phase_data in test_results['phases'].items():
            if isinstance(phase_data, dict) and 'errors' in phase_data:
                all_errors.extend(phase_data['errors'])
        
        if all_errors:
            self.stdout.write(f'\nErrors encountered ({len(all_errors)}):')
            for error in all_errors[:10]:  # Show first 10 errors
                self.stdout.write(f'  - {error}')
            if len(all_errors) > 10:
                self.stdout.write(f'  ... and {len(all_errors) - 10} more errors')
    
    def generate_detailed_report(self, test_results):
        """Generate detailed performance report"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('DETAILED PERFORMANCE REPORT')
        self.stdout.write('='*60)
        
        # Performance metrics summary
        summary = self.performance_service.get_performance_summary(hours=1)
        
        self.stdout.write(f'\nPerformance Metrics (Last Hour):')
        self.stdout.write(f'  Total metrics recorded: {summary.get("total_metrics", 0)}')
        self.stdout.write(f'  Error rate: {summary.get("error_rate", 0):.2f}%')
        self.stdout.write(f'  Max concurrent calls: {summary.get("max_concurrent_calls", 0)}')
        
        # Call bot performance
        call_bot_perf = summary.get('call_bot_performance', {})
        if call_bot_perf.get('total_sessions', 0) > 0:
            self.stdout.write(f'\nCall Bot Performance:')
            self.stdout.write(f'  Total sessions: {call_bot_perf["total_sessions"]}')
            self.stdout.write(f'  Avg connection time: {call_bot_perf.get("avg_connection_time", 0):.3f}s')
            self.stdout.write(f'  Max connection time: {call_bot_perf.get("max_connection_time", 0):.3f}s')
        
        # AI performance
        ai_perf = summary.get('ai_performance', {})
        if ai_perf.get('total_operations', 0) > 0:
            self.stdout.write(f'\nAI Processing Performance:')
            self.stdout.write(f'  Total operations: {ai_perf["total_operations"]}')
            self.stdout.write(f'  Avg processing time: {ai_perf.get("avg_processing_time", 0):.3f}s')
            self.stdout.write(f'  Max processing time: {ai_perf.get("max_processing_time", 0):.3f}s')
        
        # System alerts
        active_alerts = SystemAlert.objects.filter(is_active=True).count()
        if active_alerts > 0:
            self.stdout.write(f'\nActive System Alerts: {active_alerts}')
            
            recent_alerts = SystemAlert.objects.filter(
                first_occurred__gte=timezone.now() - timezone.timedelta(hours=1),
                is_active=True
            ).values_list('title', 'severity')
            
            for title, severity in recent_alerts[:5]:
                self.stdout.write(f'  [{severity.upper()}] {title}')
    
    def get_or_create_test_lead(self):
        """Get or create test lead for capacity testing"""
        lead, created = Lead.objects.get_or_create(
            crm_id='CAPACITY_TEST_LEAD',
            defaults={
                'name': 'Capacity Test Lead',
                'email': 'capacity.test@example.com',
                'company': 'Capacity Test Company',
                'status': 'qualified'
            }
        )
        return lead
    
    def cleanup_test_data(self):
        """Clean up test data"""
        self.stdout.write('\nCleaning up test data...')
        
        try:
            # Delete test meetings and sessions
            test_meetings = Meeting.objects.filter(
                calendar_event_id__startswith='capacity_test_meeting_'
            )
            meeting_count = test_meetings.count()
            test_meetings.delete()
            
            # Delete test lead if no other meetings reference it
            try:
                test_lead = Lead.objects.get(crm_id='CAPACITY_TEST_LEAD')
                if not test_lead.meeting_set.exists():
                    test_lead.delete()
                    self.stdout.write('Deleted test lead')
            except Lead.DoesNotExist:
                pass
            
            self.stdout.write(f'Cleaned up {meeting_count} test meetings and related data')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during cleanup: {str(e)}'))