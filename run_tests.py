#!/usr/bin/env python
"""
Test runner script for the Intelligent Meeting Workflow project.
This script runs all tests and provides a summary of the results.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run Django tests and return results"""
    print("=" * 60)
    print("Running Intelligent Meeting Workflow Tests")
    print("=" * 60)
    
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelligent_meeting_workflow.settings')
    
    try:
        # Run tests with coverage if available
        result = subprocess.run([
            sys.executable, 'manage.py', 'test', 
            '--verbosity=2',
            '--keepdb'
        ], capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ SOME TESTS FAILED!")
            print("=" * 60)
            return False
            
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def check_project_structure():
    """Check if all required files and directories exist"""
    print("\nChecking project structure...")
    
    required_files = [
        'manage.py',
        'requirements.txt',
        'intelligent_meeting_workflow/settings.py',
        'leads/models.py',
        'meetings/models.py',
        'ai_assistant/models.py',
    ]
    
    required_dirs = [
        'leads/migrations',
        'meetings/migrations',
        'ai_assistant/migrations',
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
    
    if missing_files or missing_dirs:
        print("❌ Missing required files/directories:")
        for item in missing_files + missing_dirs:
            print(f"  - {item}")
        return False
    else:
        print("✅ Project structure is complete")
        return True

def main():
    """Main function"""
    print("Intelligent Meeting Workflow - Test Runner")
    print("=" * 60)
    
    # Check project structure first
    if not check_project_structure():
        sys.exit(1)
    
    # Run tests
    if run_tests():
        print("\n🎉 Project setup is complete and all tests pass!")
        print("\nNext steps:")
        print("1. Set up PostgreSQL database")
        print("2. Create .env file with your configuration")
        print("3. Run migrations: python manage.py migrate")
        print("4. Create superuser: python manage.py createsuperuser")
        print("5. Start development server: python manage.py runserver")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()