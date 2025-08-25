"""
Role-Based Access Control and Permissions for Meeting Intelligence System
"""
from rest_framework import permissions
from django.contrib.auth.models import User
from .models import UserProfile


class MeetingIntelligencePermission(permissions.BasePermission):
    """
    Base permission class for meeting intelligence system
    """
    
    def has_permission(self, request, view):
        """
        Check if user has permission to access the view
        """
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Ensure user has a profile
        if not hasattr(request.user, 'profile'):
            UserProfile.objects.create(user=request.user)
            
        return True


class RoleBasedPermission(MeetingIntelligencePermission):
    """
    Permission class that checks user roles
    """
    required_roles = []
    required_permissions = []
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        user_profile = request.user.profile
        
        # Check role-based access
        if self.required_roles and user_profile.role not in self.required_roles:
            return False
            
        # Check specific permissions
        if self.required_permissions:
            for permission in self.required_permissions:
                if not user_profile.has_permission(permission):
                    return False
                    
        return True


class AdminOnlyPermission(RoleBasedPermission):
    """
    Permission for admin-only access
    """
    required_roles = ['admin']


class ManagerOrAdminPermission(RoleBasedPermission):
    """
    Permission for managers and admins
    """
    required_roles = ['admin', 'sales_manager']


class SalesRepOrAbovePermission(RoleBasedPermission):
    """
    Permission for sales reps and above
    """
    required_roles = ['admin', 'sales_manager', 'sales_rep']


class MeetingAccessPermission(MeetingIntelligencePermission):
    """
    Permission for meeting-specific access control
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific meeting
        """
        user_profile = request.user.profile
        
        # Admins can access all meetings
        if user_profile.role == 'admin':
            return True
            
        # Sales managers can access team meetings
        if user_profile.role == 'sales_manager':
            # Check if meeting belongs to team member
            if hasattr(obj, 'organizer'):
                return obj.organizer == request.user or self._is_team_member(request.user, obj.organizer)
            return True
            
        # Sales reps can only access their own meetings
        if user_profile.role == 'sales_rep':
            if hasattr(obj, 'organizer'):
                return obj.organizer == request.user
            return False
            
        # Viewers have read-only access to assigned meetings
        if user_profile.role == 'viewer':
            return request.method in permissions.SAFE_METHODS
            
        return False
    
    def _is_team_member(self, manager, user):
        """
        Check if user is a team member of the manager
        This is a placeholder - implement based on your team structure
        """
        # For now, assume all sales_reps are team members
        return hasattr(user, 'profile') and user.profile.role == 'sales_rep'


class LeadAccessPermission(MeetingIntelligencePermission):
    """
    Permission for lead-specific access control
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific lead
        """
        user_profile = request.user.profile
        
        # Admins can access all leads
        if user_profile.role == 'admin':
            return True
            
        # Sales managers can access team leads
        if user_profile.role == 'sales_manager':
            # Check if lead is assigned to team member
            if hasattr(obj, 'assigned_to'):
                return obj.assigned_to == request.user or self._is_team_member(request.user, obj.assigned_to)
            return True
            
        # Sales reps can access their assigned leads
        if user_profile.role == 'sales_rep':
            if hasattr(obj, 'assigned_to'):
                return obj.assigned_to == request.user
            return False
            
        # Viewers have read-only access
        if user_profile.role == 'viewer':
            return request.method in permissions.SAFE_METHODS
            
        return False
    
    def _is_team_member(self, manager, user):
        """
        Check if user is a team member of the manager
        """
        return hasattr(user, 'profile') and user.profile.role == 'sales_rep'


class DebriefingAccessPermission(MeetingIntelligencePermission):
    """
    Permission for debriefing-specific access control
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific debriefing session
        """
        user_profile = request.user.profile
        
        # Admins can access all debriefings
        if user_profile.role == 'admin':
            return True
            
        # Sales managers can access team debriefings
        if user_profile.role == 'sales_manager':
            if hasattr(obj, 'meeting') and hasattr(obj.meeting, 'organizer'):
                return (obj.meeting.organizer == request.user or 
                       self._is_team_member(request.user, obj.meeting.organizer))
            return True
            
        # Sales reps can only access their own debriefings
        if user_profile.role == 'sales_rep':
            if hasattr(obj, 'meeting') and hasattr(obj.meeting, 'organizer'):
                return obj.meeting.organizer == request.user
            return False
            
        # Viewers have read-only access to completed debriefings
        if user_profile.role == 'viewer':
            return (request.method in permissions.SAFE_METHODS and 
                   getattr(obj, 'completed_at', None) is not None)
            
        return False
    
    def _is_team_member(self, manager, user):
        """
        Check if user is a team member of the manager
        """
        return hasattr(user, 'profile') and user.profile.role == 'sales_rep'


class CompetitiveIntelligencePermission(MeetingIntelligencePermission):
    """
    Permission for competitive intelligence access
    """
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
            
        user_profile = request.user.profile
        
        # Only sales_manager and admin can access competitive intelligence
        return user_profile.role in ['admin', 'sales_manager']


def check_user_permission(user, permission_name):
    """
    Utility function to check if user has specific permission
    """
    if not user or not user.is_authenticated:
        return False
        
    if not hasattr(user, 'profile'):
        return False
        
    return user.profile.has_permission(permission_name)


def get_user_role(user):
    """
    Utility function to get user role
    """
    if not user or not user.is_authenticated:
        return None
        
    if not hasattr(user, 'profile'):
        return None
        
    return user.profile.role


def require_role(allowed_roles):
    """
    Decorator to require specific roles for view functions
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            user_role = get_user_role(request.user)
            if user_role not in allowed_roles:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Insufficient permissions")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission_name):
    """
    Decorator to require specific permission for view functions
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not check_user_permission(request.user, permission_name):
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Insufficient permissions")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator