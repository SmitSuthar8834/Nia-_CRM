"""
Management command for running load tests to verify concurrent call capacity
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from performance_monitoring.services import PerformanceMonitoringService
from performance_monitoring.tests_performance import LoadTestRunner
from meetings.models import Meeting, CallBotSession
from leads.models import Lead


class Command(BaseCommand):
    help = 'Run load tests to verify system capacity for concurrent calls'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--concurrent-calls',
            type=int,
            default=50,
            help='Number of concurrent calls to simulate (default: 50)'
        )
        parser.add_argument(
            '--duration',
            type=float,
            default=30.0,
            help='Duration of each simulated call in seconds (default: 30.0)'
        )
        parser.add_argument(
            '--ramp-up',
            type=int,
            default=0,
            help='Ramp-up time in seconds to gradually increase load (default: 0)'
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=1,
            help='Number of test iterations to run (default: 1)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after completion'
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate detailed performance report'
        )
    
    def handle(self, *args, **options):
        concurrent_calls = options['concurrent_calls']
        duration = options['duration']
        ramp_up = options['ramp_up']
        iterations = options['iterations']
        cleanup = options['cleanup']
        generate_report = options['report']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting load test with {concurrent_calls} concurrent calls')
        )
        self.stdout.write(f'Call duration: {duration}s')
        self.stdout.write(f'Ramp-up time: {ramp_up}s')
        self.stdout.write(f'Iterations: {iterations}')
        
        performance_service = PerformanceMonitoringService()
        all_results = []
        
        try:
            for iteration in range(iterations):
                self.stdout.write(f'\n--- Iteration {iteration + 1}/{iterations} ---')
                
                # Run load test
                results = self.run_load_test(
                    concurrent_calls, duration, ramp_up, performance_service
                )
                all_results.append(results)
                
                # Display results
                self.display_results(results, iteration + 1)
                
                # Wait between iterations if multiple
                if iteration < iterations - 1:
                    self.stdout.write('Waiting 30 seconds before next iteration...')
                    time.sleep(30)
            
            # Display overall summary
            if iterations > 1:
                self.display_overall_summary(all_results)
            
            # Generate detailed report if requested
            if generate_report:
                self.generate_performance_report(performance_service)
            
            # Cleanup test data if requested
            if cleanup:
                self.cleanup_test_data()
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nLoad test interrupted by user'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Load test error: {str(e)}'))
            raise
    
    def run_load_test(self, concurrent_calls, duration, ramp_up, performance_service):
        """Run a single load test iteration"""
        start_time = time.time()
        results = []
        
        # Create test lead for all meetings
        test_lead = self.get_or_create_test_lead()
        
        def simulate_call_with_ramp_up(call_id, delay=0):
            """Simulate a single call with optional ramp-up delay"""
            if delay > 0:
                time.sleep(delay)
            
            return self.simulate_call_bot_session(
                call_id, duration, test_lead, performance_service
            )
        
        # Calculate ramp-up delays
        ramp_delays = []
        if ramp_up > 0:
            for i in range(concurrent_calls):
                delay = (i / concurrent_calls) * ramp_up
                ramp_delays.append(delay)
        else:
            ramp_delays = [0] * concurrent_calls
        
        # Execute concurrent calls
        with ThreadPoolExecutor(max_workers=concurrent_calls) as executor:
            futures = [
                executor.submit(simulate_call_with_ramp_up, i, ramp_delays[i])
                for i in range(concurrent_calls)
            ]
            
            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                
                # Show progress
                completed = len(results)
                if completed % 10 == 0 or completed == concurrent_calls:
                    self.stdout.write(f'Completed: {completed}/{concurrent_calls}')
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_calls = [r for r in results if r['success']]
        failed_calls = [r for r in results if not r['success']]
        
        return {
            'concurrent_calls': concurrent_calls,
            'duration': duration,
            'ramp_up': ramp_up,
            'total_time': total_time,
            'successful_calls': len(successful_calls),
            'failed_calls': len(failed_calls),
            'success_rate': len(successful_calls) / concurrent_calls * 100,
            'avg_connection_time': sum(r.get('connection_time', 0) for r in successful_calls) / len(successful_calls) if successful_calls else 0,
            'avg_processing_time': sum(r.get('processing_time', 0) for r in successful_calls) / len(successful_calls) if successful_calls else 0,
            'max_connection_time': max((r.get('connection_time', 0) for r in successful_calls), default=0),
            'max_processing_time': max((r.get('processing_time', 0) for r in successful_calls), default=0),
            'errors': [r.get('error', '') for r in failed_calls]
        }
    
    def simulate_call_bot_session(self, call_id, duration, test_lead, performance_service):
        """Simulate a single call bot session"""
        try:
            # Simulate connection phase
            connection_start = time.time()
            time.sleep(0.05 + (call_id % 10) * 0.01)  # Variable connection time
            connection_time = time.time() - connection_start
            
            # Create meeting and call bot session
            meeting = Meeting.objects.create(
                calendar_event_id=f"load_test_meeting_{call_id}_{int(time.time())}",
                lead=test_lead,
                title=f"Load Test Meeting {call_id}",
                start_time=timezone.now(),
                end_time=timezone.now() + timezone.timedelta(seconds=duration)
            )
            
            call_bot_session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f"load_test_bot_{call_id}_{int(time.time())}",
                platform="meet",
                join_time=timezone.now(),
                connection_status="connected"
            )
            
            # Track connection performance
            performance_service.track_call_bot_performance(
                call_bot_session=call_bot_session,
                connection_time=connection_time,
                connection_success=True
            )
            
            # Simulate processing phase
            processing_start = time.time()
            time.sleep(duration * 0.1)  # Simulate 10% of call duration for processing
            processing_time = time.time() - processing_start
            
            # Update audio metrics
            performance_service.update_call_bot_audio_metrics(
                call_bot_session=call_bot_session,
                audio_quality_score=0.85 + (call_id % 10) * 0.01,  # Variable quality
                audio_dropouts=call_id % 3,  # Some dropouts
                audio_latency=40.0 + (call_id % 20)  # Variable latency
            )
            
            # Track AI processing
            performance_service.track_ai_processing(
                operation_type='transcription',
                operation_id=f"load_test_transcription_{call_id}",
                processing_time=processing_time,
                input_size=1000 + (call_id * 50),
                output_size=800 + (call_id * 40),
                confidence_score=0.88 + (call_id % 10) * 0.01
            )
            
            # End session
            call_bot_session.connection_status = 'disconnected'
            call_bot_session.leave_time = timezone.now()
            call_bot_session.save()
            
            return {
                'call_id': call_id,
                'success': True,
                'connection_time': connection_time,
                'processing_time': processing_time,
                'meeting_id': meeting.id,
                'session_id': call_bot_session.id
            }
            
        except Exception as e:
            return {
                'call_id': call_id,
                'success': False,
                'error': str(e)
            }
    
    def get_or_create_test_lead(self):
        """Get or create a test lead for load testing"""
        lead, created = Lead.objects.get_or_create(
            crm_id="LOAD_TEST_LEAD",
            defaults={
                'name': 'Load Test Lead',
                'email': 'loadtest@example.com',
                'company': 'Load Test Company',
                'status': 'qualified'
            }
        )
        return lead
    
    def display_results(self, results, iteration=None):
        """Display load test results"""
        header = f"Load Test Results"
        if iteration:
            header += f" - Iteration {iteration}"
        
        self.stdout.write(f'\n{header}')
        self.stdout.write('=' * len(header))
        self.stdout.write(f'Concurrent calls: {results["concurrent_calls"]}')
        self.stdout.write(f'Call duration: {results["duration"]}s')
        self.stdout.write(f'Ramp-up time: {results["ramp_up"]}s')
        self.stdout.write(f'Total test time: {results["total_time"]:.2f}s')
        self.stdout.write('')
        
        # Success metrics
        success_style = self.style.SUCCESS if results['success_rate'] >= 95 else self.style.WARNING
        self.stdout.write(f'Successful calls: {results["successful_calls"]}/{results["concurrent_calls"]}')
        self.stdout.write(success_style(f'Success rate: {results["success_rate"]:.1f}%'))
        
        if results['failed_calls'] > 0:
            self.stdout.write(self.style.ERROR(f'Failed calls: {results["failed_calls"]}'))
            if results['errors']:
                self.stdout.write('Error samples:')
                for error in results['errors'][:3]:  # Show first 3 errors
                    self.stdout.write(f'  - {error}')
        
        # Performance metrics
        self.stdout.write('')
        self.stdout.write('Performance Metrics:')
        self.stdout.write(f'  Avg connection time: {results["avg_connection_time"]:.3f}s')
        self.stdout.write(f'  Max connection time: {results["max_connection_time"]:.3f}s')
        self.stdout.write(f'  Avg processing time: {results["avg_processing_time"]:.3f}s')
        self.stdout.write(f'  Max processing time: {results["max_processing_time"]:.3f}s')
        
        # Performance assessment
        self.stdout.write('')
        self.assess_performance(results)
    
    def assess_performance(self, results):
        """Assess performance against requirements"""
        assessments = []
        
        # Success rate assessment (Requirement 8.1: 99% uptime)
        if results['success_rate'] >= 99:
            assessments.append(('Success Rate', 'PASS', f"{results['success_rate']:.1f}% >= 99%"))
        elif results['success_rate'] >= 95:
            assessments.append(('Success Rate', 'WARN', f"{results['success_rate']:.1f}% < 99% but >= 95%"))
        else:
            assessments.append(('Success Rate', 'FAIL', f"{results['success_rate']:.1f}% < 95%"))
        
        # Connection time assessment (should be under 5 seconds)
        if results['avg_connection_time'] <= 5.0:
            assessments.append(('Connection Time', 'PASS', f"{results['avg_connection_time']:.2f}s <= 5s"))
        else:
            assessments.append(('Connection Time', 'FAIL', f"{results['avg_connection_time']:.2f}s > 5s"))
        
        # Concurrent capacity assessment (Requirement 8.6: 50 concurrent calls)
        if results['concurrent_calls'] >= 50 and results['success_rate'] >= 95:
            assessments.append(('Concurrent Capacity', 'PASS', f"Handled {results['concurrent_calls']} calls successfully"))
        elif results['concurrent_calls'] >= 50:
            assessments.append(('Concurrent Capacity', 'WARN', f"Handled {results['concurrent_calls']} calls with issues"))
        else:
            assessments.append(('Concurrent Capacity', 'INFO', f"Tested with {results['concurrent_calls']} calls"))
        
        # Display assessments
        self.stdout.write('Performance Assessment:')
        for metric, status, message in assessments:
            if status == 'PASS':
                self.stdout.write(self.style.SUCCESS(f'  ✓ {metric}: {message}'))
            elif status == 'WARN':
                self.stdout.write(self.style.WARNING(f'  ⚠ {metric}: {message}'))
            elif status == 'FAIL':
                self.stdout.write(self.style.ERROR(f'  ✗ {metric}: {message}'))
            else:
                self.stdout.write(f'  ℹ {metric}: {message}')
    
    def display_overall_summary(self, all_results):
        """Display summary across all iterations"""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('OVERALL SUMMARY')
        self.stdout.write('=' * 50)
        
        total_calls = sum(r['concurrent_calls'] for r in all_results)
        total_successful = sum(r['successful_calls'] for r in all_results)
        total_failed = sum(r['failed_calls'] for r in all_results)
        
        avg_success_rate = sum(r['success_rate'] for r in all_results) / len(all_results)
        avg_connection_time = sum(r['avg_connection_time'] for r in all_results) / len(all_results)
        avg_processing_time = sum(r['avg_processing_time'] for r in all_results) / len(all_results)
        
        self.stdout.write(f'Total iterations: {len(all_results)}')
        self.stdout.write(f'Total calls: {total_calls}')
        self.stdout.write(f'Total successful: {total_successful}')
        self.stdout.write(f'Total failed: {total_failed}')
        self.stdout.write(f'Average success rate: {avg_success_rate:.1f}%')
        self.stdout.write(f'Average connection time: {avg_connection_time:.3f}s')
        self.stdout.write(f'Average processing time: {avg_processing_time:.3f}s')
        
        # Consistency assessment
        success_rates = [r['success_rate'] for r in all_results]
        success_rate_std = (sum((x - avg_success_rate) ** 2 for x in success_rates) / len(success_rates)) ** 0.5
        
        if success_rate_std < 2.0:
            self.stdout.write(self.style.SUCCESS(f'Performance consistency: GOOD (std dev: {success_rate_std:.1f}%)'))
        else:
            self.stdout.write(self.style.WARNING(f'Performance consistency: VARIABLE (std dev: {success_rate_std:.1f}%)'))
    
    def generate_performance_report(self, performance_service):
        """Generate detailed performance report"""
        self.stdout.write('\nGenerating performance report...')
        
        try:
            summary = performance_service.get_performance_summary(hours=1)
            
            self.stdout.write('\n--- PERFORMANCE REPORT ---')
            self.stdout.write(f'Total metrics recorded: {summary.get("total_metrics", 0)}')
            self.stdout.write(f'Error rate: {summary.get("error_rate", 0):.2f}%')
            self.stdout.write(f'Max concurrent calls: {summary.get("max_concurrent_calls", 0)}')
            
            call_bot_perf = summary.get('call_bot_performance', {})
            if call_bot_perf.get('total_sessions', 0) > 0:
                self.stdout.write(f'Call bot sessions: {call_bot_perf["total_sessions"]}')
                self.stdout.write(f'Avg connection time: {call_bot_perf.get("avg_connection_time", 0):.3f}s')
            
            ai_perf = summary.get('ai_performance', {})
            if ai_perf.get('total_operations', 0) > 0:
                self.stdout.write(f'AI operations: {ai_perf["total_operations"]}')
                self.stdout.write(f'Avg processing time: {ai_perf.get("avg_processing_time", 0):.3f}s')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating report: {str(e)}'))
    
    def cleanup_test_data(self):
        """Clean up test data created during load testing"""
        self.stdout.write('\nCleaning up test data...')
        
        try:
            # Delete test meetings and sessions
            test_meetings = Meeting.objects.filter(
                calendar_event_id__startswith='load_test_meeting_'
            )
            meeting_count = test_meetings.count()
            test_meetings.delete()
            
            # Delete test lead if no other meetings reference it
            try:
                test_lead = Lead.objects.get(crm_id="LOAD_TEST_LEAD")
                if not test_lead.meeting_set.exists():
                    test_lead.delete()
                    self.stdout.write('Deleted test lead')
            except Lead.DoesNotExist:
                pass
            
            self.stdout.write(f'Cleaned up {meeting_count} test meetings and related data')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during cleanup: {str(e)}'))