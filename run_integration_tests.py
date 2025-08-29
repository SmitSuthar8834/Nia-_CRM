#!/usr/bin/env python
"""
Integration test runner for the intelligent meeting workflow system
Runs comprehensive end-to-end tests to verify system functionality
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner


def setup_test_environment():
    """Set up Django test environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelligent_meeting_workflow.settings')
    django.setup()


def run_integration_tests():
    """Run all integration tests"""
    
    # Test modules to run
    test_modules = [
        'tests.integration.test_end_to_end_workflow',
        'tests.integration.test_crm_staging_integration',
        'tests.integration.test_validation_session_mocks',
        'tests.integration.test_deployment_verification'
    ]
    
    print("=" * 70)
    print("INTELLIGENT MEETING WORKFLOW - INTEGRATION TESTS")
    print("=" * 70)
    print()
    
    # Get Django test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    # Run tests
    failures = test_runner.run_tests(test_modules)
    
    print()
    print("=" * 70)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 70)
    
    if failures:
        print(f"❌ {failures} test(s) failed")
        return False
    else:
        print("✅ All integration tests passed!")
        return True


def run_specific_test_suite(suite_name):
    """Run a specific test suite"""
    
    suite_mapping = {
        'e2e': 'tests.integration.test_end_to_end_workflow',
        'crm': 'tests.integration.test_crm_staging_integration',
        'validation': 'tests.integration.test_validation_session_mocks',
        'deployment': 'tests.integration.test_deployment_verification'
    }
    
    if suite_name not in suite_mapping:
        print(f"Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(suite_mapping.keys())}")
        return False
    
    test_module = suite_mapping[suite_name]
    
    print(f"Running {suite_name} integration tests...")
    print("=" * 50)
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    failures = test_runner.run_tests([test_module])
    
    if failures:
        print(f"❌ {failures} test(s) failed in {suite_name} suite")
        return False
    else:
        print(f"✅ All {suite_name} tests passed!")
        return True


def main():
    """Main entry point"""
    setup_test_environment()
    
    if len(sys.argv) > 1:
        # Run specific test suite
        suite_name = sys.argv[1]
        success = run_specific_test_suite(suite_name)
    else:
        # Run all integration tests
        success = run_integration_tests()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()