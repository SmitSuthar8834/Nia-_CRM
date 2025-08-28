# Debriefings App - Automated Scheduling and Management

## Overview

The debriefings app provides automated debriefing scheduling and management for sales meetings with AI-powered conversation interfaces and smart notification systems.

## Features Implemented

### ✅ Task 8: Automated Debriefing Scheduling and Management

This task implements comprehensive automated debriefing scheduling with the following components:

#### 1. Automatic Debriefing Scheduling (30 minutes after meeting end)
- **AutomatedDebriefingScheduler**: Automatically schedules debriefings within 30 minutes of meeting completion
- **Business Hours Adjustment**: Adjusts scheduling to business hours (9 AM - 6 PM)
- **Weekend Handling**: Skips weekends and schedules for next business day
- **User Pattern Analysis**: Learns from user's historical debriefing patterns

#### 2. Notification System with Decreasing Frequency
- **DebriefingNotificationService**: Manages multi-channel notifications (email, in-app, push)
- **Reminder Intervals**: 30 minutes, 2 hours, 6 hours after scheduled time
- **Email Templates**: Professional HTML and text email templates for all notification types
- **Quiet Hours**: Respects user's quiet hours preferences
- **Weekend Notifications**: Optional weekend notification settings

#### 3. Smart Rescheduling Logic
- **SmartReschedulingService**: Provides intelligent time suggestions for rescheduling
- **Pattern-Based Suggestions**: Based on user's typical debriefing timing
- **Business Hours Optimization**: Suggests times within business hours
- **Multiple Options**: Provides 5 different time suggestions with confidence scores

#### 4. Back-to-Back Meeting Consolidation
- **Consolidation Detection**: Identifies meetings within 60-minute window
- **Participant Overlap Analysis**: Requires 30% participant overlap for consolidation
- **Meeting Type Compatibility**: Ensures compatible meeting types can be consolidated
- **Consolidated Session Management**: Manages multiple meetings in single debriefing

#### 5. Reminder Notification System
- **Decreasing Frequency**: Initial → Follow-up → Final reminders
- **Multi-Channel Delivery**: Email, in-app notifications, push notifications
- **Notification Logging**: Tracks delivery status and user interactions
- **Cancellation Support**: Can cancel reminders when debriefing is completed

#### 6. Quick Survey Fallback
- **QuickSurveyService**: Creates 2-minute surveys for skipped debriefings
- **Meeting Type Customization**: Tailors questions based on meeting type
- **Essential Data Capture**: Captures meeting outcome, next steps, insights
- **Expiration Handling**: 24-hour expiration for surveys

#### 7. Debriefing Session State Management
- **DebriefingStateManager**: Manages session state transitions
- **Valid Transitions**: Enforces valid state changes (scheduled → in_progress → completed)
- **Automatic Timestamps**: Records start and completion times
- **Meeting Status Updates**: Updates meeting completion status

#### 8. Comprehensive Unit Tests
- **16 Test Cases**: Covering all major functionality
- **Model Testing**: Tests for all debriefing models and relationships
- **Workflow Testing**: End-to-end debriefing workflow tests
- **Edge Case Handling**: Tests for overdue sessions, consolidation, state transitions
- **Data Structure Validation**: Tests for JSON field structures and data integrity

## Files Created

### Core Implementation
- `apps/debriefings/notifications.py` - Notification service and smart rescheduling
- `apps/debriefings/test_core.py` - Comprehensive unit tests (16 test cases)

### Email Templates
- `apps/debriefings/templates/debriefings/emails/initial_reminder.html/.txt`
- `apps/debriefings/templates/debriefings/emails/followup_reminder.html/.txt`
- `apps/debriefings/templates/debriefings/emails/final_reminder.html/.txt`
- `apps/debriefings/templates/debriefings/emails/quick_survey.html/.txt`
- `apps/debriefings/templates/debriefings/emails/overdue_reminder.html/.txt`
- `apps/debriefings/templates/debriefings/emails/digest.html/.txt`

### Existing Enhanced Files
- `apps/debriefings/scheduling.py` - Enhanced with consolidation logic
- `apps/debriefings/services.py` - Enhanced with state management
- `apps/debriefings/tasks.py` - Enhanced with notification tasks
- `apps/debriefings/models.py` - Enhanced with comprehensive models

## Key Features

### Automated Scheduling
- Detects completed sales meetings automatically
- Schedules debriefings within 30 minutes of meeting end
- Adjusts for business hours and weekends
- Consolidates back-to-back meetings intelligently

### Smart Notifications
- Multi-channel notification system (email, in-app, push)
- Decreasing frequency reminders (30min, 2hr, 6hr)
- Professional email templates with HTML and text versions
- Respects user preferences for quiet hours and weekends

### Intelligent Rescheduling
- Analyzes user patterns for optimal scheduling
- Provides multiple time suggestions with confidence scores
- Considers business hours and availability
- Learns from user behavior over time

### Fallback Mechanisms
- Quick survey for skipped debriefings
- Overdue session handling with expiration
- Graceful degradation when services are unavailable
- Comprehensive error handling and logging

### State Management
- Robust state transition validation
- Automatic timestamp recording
- Meeting status synchronization
- Data integrity enforcement

## Testing

The implementation includes comprehensive unit tests covering:

- **Model Tests**: Creation, relationships, properties, methods
- **Scheduling Logic**: Eligibility, consolidation, business hours
- **Workflow Tests**: End-to-end debriefing processes
- **Data Structure Tests**: JSON fields, conversation data, extracted data
- **Edge Cases**: Overdue sessions, state transitions, error conditions

Run tests with:
```bash
python manage.py test apps.debriefings.test_core -v 2
```

## Requirements Satisfied

This implementation satisfies all requirements from **Requirement 3: Automated Debriefing Scheduling and Management**:

- ✅ 3.1: Automatic scheduling within 30 minutes of meeting end
- ✅ 3.2: Notifications and easy access to debriefing interface
- ✅ 3.3: Rescheduling options with smart suggestions
- ✅ 3.4: Intelligent consolidation of back-to-back meetings
- ✅ 3.5: Reminder notifications with decreasing frequency
- ✅ 3.6: Quick survey fallback for skipped debriefings

## Integration Points

The debriefings app integrates with:

- **Meetings App**: Detects completed sales meetings
- **AI Engine**: Powers intelligent questioning and data extraction
- **CRM Sync**: Updates CRM with extracted meeting data
- **Calendar Integration**: Considers calendar availability for scheduling
- **Analytics**: Tracks debriefing completion metrics and patterns

## Next Steps

With Task 8 completed, the system now has comprehensive automated debriefing scheduling and management. The next recommended tasks are:

- **Task 9**: Build debriefing conversation interface and management
- **Task 10**: Implement CRM data updates and field mapping
- **Task 11**: Build review and approval workflows

The foundation is now in place for a complete meeting intelligence system with automated scheduling, smart notifications, and comprehensive testing coverage.