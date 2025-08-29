"""
Email service classes for draft email creation, approval, and scheduling
"""
import uuid
from datetime import timedelta
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from .models import DraftEmail, EmailApproval, ValidationSession


class EmailDraftService:
    """
    Service for creating draft emails based on meeting outcomes
    """
    
    def create_draft_email(self, validation_session: ValidationSession, email_type: str,
                          recipient_email: str, recipient_name: str = '',
                          cc_emails: list = None, bcc_emails: list = None,
                          custom_template: str = '', include_meeting_summary: bool = True,
                          include_action_items: bool = True, include_next_steps: bool = True) -> DraftEmail:
        """
        Create a draft email based on validation session data
        """
        try:
            # Get meeting and summary data
            draft_summary = validation_session.draft_summary
            meeting = draft_summary.bot_session.meeting
            
            # Generate email content
            subject = self._generate_subject(email_type, meeting, validation_session)
            body_html, body_text = self._generate_body(
                email_type=email_type,
                meeting=meeting,
                validation_session=validation_session,
                draft_summary=draft_summary,
                recipient_name=recipient_name,
                custom_template=custom_template,
                include_meeting_summary=include_meeting_summary,
                include_action_items=include_action_items,
                include_next_steps=include_next_steps
            )
            
            # Create draft email
            draft_email = DraftEmail.objects.create(
                validation_session=validation_session,
                email_type=email_type,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                cc_emails=cc_emails or [],
                bcc_emails=bcc_emails or [],
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                status='draft'
            )
            
            return draft_email
            
        except Exception as e:
            print(f"Error creating draft email: {str(e)}")
            return None
    
    def _generate_subject(self, email_type: str, meeting, validation_session: ValidationSession) -> str:
        """
        Generate email subject based on type and meeting data
        """
        subject_templates = {
            'follow_up': f"Follow-up: {meeting.title}",
            'thank_you': f"Thank you for the meeting - {meeting.title}",
            'next_steps': f"Next steps from our meeting - {meeting.title}",
            'meeting_summary': f"Meeting summary: {meeting.title}",
            'action_items': f"Action items from {meeting.title}"
        }
        
        return subject_templates.get(email_type, f"Follow-up: {meeting.title}")
    
    def _generate_body(self, email_type: str, meeting, validation_session: ValidationSession,
                      draft_summary, recipient_name: str, custom_template: str,
                      include_meeting_summary: bool, include_action_items: bool,
                      include_next_steps: bool) -> tuple:
        """
        Generate email body HTML and text content
        """
        # Prepare context data
        context = {
            'recipient_name': recipient_name or 'there',
            'meeting': meeting,
            'validation_session': validation_session,
            'draft_summary': draft_summary,
            'include_meeting_summary': include_meeting_summary,
            'include_action_items': include_action_items,
            'include_next_steps': include_next_steps,
            'validated_summary': validation_session.validated_summary,
            'approved_crm_updates': validation_session.approved_crm_updates,
            'rep_responses': validation_session.rep_responses
        }
        
        # Use custom template if provided, otherwise use default
        if custom_template:
            body_html = custom_template.format(**context)
            body_text = self._html_to_text(body_html)
        else:
            # Use default templates based on email type
            template_name = f'emails/{email_type}.html'
            try:
                body_html = render_to_string(template_name, context)
                body_text = render_to_string(f'emails/{email_type}.txt', context)
            except:
                # Fallback to generic template
                body_html = self._generate_default_html(context)
                body_text = self._generate_default_text(context)
        
        return body_html, body_text
    
    def _generate_default_html(self, context) -> str:
        """
        Generate default HTML email content
        """
        html = f"""
        <html>
        <body>
            <p>Hi {context['recipient_name']},</p>
            
            <p>Thank you for taking the time to meet with us regarding <strong>{context['meeting'].title}</strong>.</p>
            
            {self._format_meeting_summary_html(context) if context['include_meeting_summary'] else ''}
            
            {self._format_action_items_html(context) if context['include_action_items'] else ''}
            
            {self._format_next_steps_html(context) if context['include_next_steps'] else ''}
            
            <p>Please let me know if you have any questions or if there's anything else I can help with.</p>
            
            <p>Best regards,<br>
            [Your Name]</p>
        </body>
        </html>
        """
        return html
    
    def _generate_default_text(self, context) -> str:
        """
        Generate default text email content
        """
        text = f"""Hi {context['recipient_name']},

Thank you for taking the time to meet with us regarding {context['meeting'].title}.

{self._format_meeting_summary_text(context) if context['include_meeting_summary'] else ''}

{self._format_action_items_text(context) if context['include_action_items'] else ''}

{self._format_next_steps_text(context) if context['include_next_steps'] else ''}

Please let me know if you have any questions or if there's anything else I can help with.

Best regards,
[Your Name]
        """
        return text
    
    def _format_meeting_summary_html(self, context) -> str:
        """Format meeting summary for HTML email"""
        if context['validated_summary']:
            return f"""
            <h3>Meeting Summary</h3>
            <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #007cba;">
                {context['validated_summary'].replace('\n', '<br>')}
            </div>
            """
        return ""
    
    def _format_meeting_summary_text(self, context) -> str:
        """Format meeting summary for text email"""
        if context['validated_summary']:
            return f"""
MEETING SUMMARY:
{context['validated_summary']}
            """
        return ""
    
    def _format_action_items_html(self, context) -> str:
        """Format action items for HTML email"""
        action_items = context['draft_summary'].extracted_action_items
        if action_items:
            items_html = ""
            for item in action_items:
                items_html += f"<li>{item.get('description', '')}"
                if item.get('assignee'):
                    items_html += f" (Assigned to: {item['assignee']})"
                if item.get('due_date'):
                    items_html += f" (Due: {item['due_date']})"
                items_html += "</li>"
            
            return f"""
            <h3>Action Items</h3>
            <ul>
                {items_html}
            </ul>
            """
        return ""
    
    def _format_action_items_text(self, context) -> str:
        """Format action items for text email"""
        action_items = context['draft_summary'].extracted_action_items
        if action_items:
            items_text = "ACTION ITEMS:\n"
            for i, item in enumerate(action_items, 1):
                items_text += f"{i}. {item.get('description', '')}"
                if item.get('assignee'):
                    items_text += f" (Assigned to: {item['assignee']})"
                if item.get('due_date'):
                    items_text += f" (Due: {item['due_date']})"
                items_text += "\n"
            return items_text
        return ""
    
    def _format_next_steps_html(self, context) -> str:
        """Format next steps for HTML email"""
        next_steps = context['rep_responses'].get('next_steps', '')
        if next_steps:
            return f"""
            <h3>Next Steps</h3>
            <div style="background-color: #e8f4f8; padding: 15px; border-left: 4px solid #28a745;">
                {next_steps.replace('\n', '<br>')}
            </div>
            """
        return ""
    
    def _format_next_steps_text(self, context) -> str:
        """Format next steps for text email"""
        next_steps = context['rep_responses'].get('next_steps', '')
        if next_steps:
            return f"""
NEXT STEPS:
{next_steps}
            """
        return ""
    
    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (basic implementation)
        """
        import re
        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html)
        # Replace HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()


class EmailApprovalService:
    """
    Service for managing email approval workflow
    """
    
    def request_approval(self, draft_email: DraftEmail, approver_email: str,
                        approval_expires_hours: int = 24) -> EmailApproval:
        """
        Create an approval request for a draft email
        """
        try:
            # Generate unique approval token
            approval_token = str(uuid.uuid4())
            
            # Calculate expiration time
            expires_at = timezone.now() + timedelta(hours=approval_expires_hours)
            
            # Create approval record
            approval = EmailApproval.objects.create(
                draft_email=draft_email,
                approver_email=approver_email,
                approval_token=approval_token,
                expires_at=expires_at
            )
            
            # Send approval request email
            self._send_approval_request_email(approval)
            
            return approval
            
        except Exception as e:
            print(f"Error creating approval request: {str(e)}")
            return None
    
    def process_approval_response(self, approval: EmailApproval, action: str,
                                rejection_reason: str = '') -> bool:
        """
        Process approval response (approve/reject)
        """
        try:
            if action == 'approve':
                approval.status = 'approved'
                approval.approved_at = timezone.now()
                approval.draft_email.status = 'approved'
                approval.draft_email.approved_at = timezone.now()
                approval.draft_email.approved_by = approval.approver_email
            elif action == 'reject':
                approval.status = 'rejected'
                approval.rejection_reason = rejection_reason
                approval.draft_email.status = 'rejected'
                approval.draft_email.rejection_reason = rejection_reason
            
            approval.save()
            approval.draft_email.save()
            
            # Send notification to requester
            self._send_approval_response_notification(approval, action)
            
            return True
            
        except Exception as e:
            print(f"Error processing approval response: {str(e)}")
            return False
    
    def _send_approval_request_email(self, approval: EmailApproval):
        """
        Send approval request email to approver
        """
        try:
            # Generate approval URL (this would be a frontend URL in production)
            approval_url = f"{settings.FRONTEND_URL}/email-approval/{approval.approval_token}"
            
            subject = f"Email Approval Request: {approval.draft_email.subject}"
            
            message = f"""
            You have received an email approval request.
            
            Email Subject: {approval.draft_email.subject}
            Recipient: {approval.draft_email.recipient_email}
            Type: {approval.draft_email.get_email_type_display()}
            
            To approve or reject this email, please click the link below:
            {approval_url}
            
            This approval request expires at {approval.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approval.approver_email],
                fail_silently=False
            )
            
        except Exception as e:
            print(f"Error sending approval request email: {str(e)}")
    
    def _send_approval_response_notification(self, approval: EmailApproval, action: str):
        """
        Send notification about approval response
        """
        try:
            # This would typically be sent to the person who requested approval
            # For now, we'll just log it
            print(f"Email approval {action}d: {approval.draft_email.subject}")
            
        except Exception as e:
            print(f"Error sending approval response notification: {str(e)}")


class EmailSchedulingService:
    """
    Service for scheduling emails for future sending
    """
    
    def schedule_email(self, draft_email: DraftEmail, scheduled_send_time) -> bool:
        """
        Schedule an approved email for future sending
        """
        try:
            if draft_email.status != 'approved':
                return False
            
            draft_email.status = 'scheduled'
            draft_email.scheduled_send_time = scheduled_send_time
            draft_email.save()
            
            # In a production system, you would add this to a task queue
            # For now, we'll just update the status
            print(f"Email scheduled for {scheduled_send_time}: {draft_email.subject}")
            
            return True
            
        except Exception as e:
            print(f"Error scheduling email: {str(e)}")
            return False


class EmailSendingService:
    """
    Service for sending emails
    """
    
    def send_email(self, draft_email: DraftEmail) -> dict:
        """
        Send an email immediately
        """
        try:
            if draft_email.status not in ['approved', 'scheduled']:
                return {'success': False, 'error': 'Email must be approved or scheduled'}
            
            # Send the email
            success = send_mail(
                subject=draft_email.subject,
                message=draft_email.body_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[draft_email.recipient_email],
                html_message=draft_email.body_html,
                fail_silently=False
            )
            
            if success:
                # Update email status
                draft_email.status = 'sent'
                draft_email.sent_at = timezone.now()
                draft_email.save()
                
                return {'success': True}
            else:
                draft_email.status = 'failed'
                draft_email.error_message = 'Failed to send email'
                draft_email.save()
                
                return {'success': False, 'error': 'Failed to send email'}
                
        except Exception as e:
            error_message = str(e)
            draft_email.status = 'failed'
            draft_email.error_message = error_message
            draft_email.save()
            
            return {'success': False, 'error': error_message}