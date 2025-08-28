"""
Management command to test Gemini API connection and functionality
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.ai_engine.gemini_client import get_gemini_client
from apps.ai_engine.services import ai_health_service


class Command(BaseCommand):
    help = 'Test Gemini API connection and basic functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed health information',
        )
        parser.add_argument(
            '--test-prompt',
            type=str,
            default='Hello, can you respond with a simple greeting?',
            help='Custom test prompt to send to Gemini',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Testing Gemini API connection...')
        )
        
        try:
            # Get client and perform health check
            client = get_gemini_client()
            health_status = client.health_check()
            
            # Display basic health status
            if health_status['status'] == 'healthy':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Gemini API is healthy (Response time: {health_status.get('response_time_ms', 'N/A')}ms)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Gemini API is unhealthy: {health_status.get('error', 'Unknown error')}"
                    )
                )
                return
            
            # Test custom prompt
            self.stdout.write('\nTesting custom prompt...')
            test_prompt = options['test_prompt']
            
            response = client.generate_response(
                prompt=test_prompt,
                temperature=0.7,
                max_tokens=100
            )
            
            if response.error:
                self.stdout.write(
                    self.style.ERROR(f"✗ Test prompt failed: {response.error}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Test prompt successful")
                )
                self.stdout.write(f"Response: {response.content[:200]}...")
                self.stdout.write(
                    f"Confidence: {response.confidence_score}, "
                    f"Tokens: {response.token_count}, "
                    f"Time: {response.response_time_ms}ms, "
                    f"Cached: {response.cached}"
                )
            
            # Show detailed information if requested
            if options['detailed']:
                self.stdout.write('\n' + '='*50)
                self.stdout.write('DETAILED HEALTH INFORMATION')
                self.stdout.write('='*50)
                
                full_health = ai_health_service.get_health_status()
                
                # Usage stats
                usage_stats = full_health.get('usage_stats', {})
                self.stdout.write(f"\nUsage Statistics:")
                self.stdout.write(f"  Requests today: {usage_stats.get('requests_today', 0)}")
                self.stdout.write(f"  Requests this minute: {usage_stats.get('requests_this_minute', 0)}")
                self.stdout.write(f"  Rate limit (per minute): {usage_stats.get('rate_limit_per_minute', 'N/A')}")
                self.stdout.write(f"  Rate limit (per day): {usage_stats.get('rate_limit_per_day', 'N/A')}")
                
                # Interaction stats
                interaction_stats = full_health.get('interaction_stats', {})
                if 'last_24h' in interaction_stats:
                    stats_24h = interaction_stats['last_24h']
                    self.stdout.write(f"\nLast 24 Hours:")
                    self.stdout.write(f"  Total interactions: {stats_24h.get('total_interactions', 0)}")
                    self.stdout.write(f"  Successful interactions: {stats_24h.get('successful_interactions', 0)}")
                    self.stdout.write(f"  Success rate: {interaction_stats.get('success_rate', 0):.2%}")
                    self.stdout.write(f"  Avg response time: {stats_24h.get('avg_response_time', 0):.0f}ms")
                    self.stdout.write(f"  Avg confidence: {stats_24h.get('avg_confidence', 0):.2f}")
                
                # Template stats
                template_stats = full_health.get('template_stats', {})
                self.stdout.write(f"\nTemplate Statistics:")
                self.stdout.write(f"  Active templates: {template_stats.get('total_active_templates', 0)}")
                self.stdout.write(f"  Avg success rate: {template_stats.get('avg_success_rate', 0):.2%}")
                
                most_used = template_stats.get('most_used_templates', [])
                if most_used:
                    self.stdout.write(f"  Most used templates:")
                    for template in most_used:
                        self.stdout.write(
                            f"    - {template['name']} ({template['template_type']}): "
                            f"{template['usage_count']} uses"
                        )
            
            self.stdout.write(
                self.style.SUCCESS('\n✓ Gemini API test completed successfully')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Gemini API test failed: {str(e)}')
            )
            raise