"""
Custom enums for API documentation.
"""
from enum import Enum


class ValidationErrorEnum(Enum):
    """Enumeration of common validation error types."""
    REQUIRED = "This field is required."
    BLANK = "This field may not be blank."
    INVALID = "Invalid value."
    UNIQUE = "This field must be unique."
    MAX_LENGTH = "Ensure this field has no more than {max_length} characters."
    MIN_LENGTH = "Ensure this field has at least {min_length} characters."
    INVALID_EMAIL = "Enter a valid email address."
    INVALID_CHOICE = "Select a valid choice."


class MeetingTypeEnum(Enum):
    """Meeting type classifications."""
    DISCOVERY = "discovery"
    DEMO = "demo"
    NEGOTIATION = "negotiation"
    FOLLOW_UP = "follow_up"
    INTERNAL = "internal"
    COMPETITIVE = "competitive"
    CLOSING = "closing"


class LeadStatusEnum(Enum):
    """Lead status classifications."""
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    OPPORTUNITY = "opportunity"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DebriefingStatusEnum(Enum):
    """Debriefing session status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class SyncStatusEnum(Enum):
    """CRM synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ActionItemStatusEnum(Enum):
    """Action item status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PriorityEnum(Enum):
    """Priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ThreatLevelEnum(Enum):
    """Competitive threat levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"