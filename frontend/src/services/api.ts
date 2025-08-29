import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
    Meeting,
    ValidationSession,
    DraftSummary,
    CRMSyncRecord,
    ValidationFormData
} from '../types/validation';

class ApiClient {
    private client: AxiosInstance;

    constructor() {
        this.client = axios.create({
            baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Add request interceptor for authentication
        this.client.interceptors.request.use(
            (config) => {
                const token = localStorage.getItem('authToken');
                if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
                return config;
            },
            (error) => Promise.reject(error)
        );

        // Add response interceptor for error handling
        this.client.interceptors.response.use(
            (response) => response,
            (error) => {
                if (error.response?.status === 401) {
                    localStorage.removeItem('authToken');
                    window.location.href = '/login';
                }
                return Promise.reject(error);
            }
        );
    }

    // Meeting endpoints
    async getMeetings(params?: {
        status?: string;
        page?: number;
        limit?: number;
    }): Promise<AxiosResponse<{ results: Meeting[]; count: number }>> {
        return this.client.get('/meetings/', { params });
    }

    async getMeeting(id: string): Promise<AxiosResponse<Meeting>> {
        return this.client.get(`/meetings/${id}/`);
    }

    // Validation session endpoints
    async getValidationSessions(params?: {
        status?: string;
        sales_rep_email?: string;
        page?: number;
        limit?: number;
    }): Promise<AxiosResponse<{ results: ValidationSession[]; count: number }>> {
        return this.client.get('/validation-sessions/', { params });
    }

    async getValidationSession(id: string): Promise<AxiosResponse<ValidationSession>> {
        return this.client.get(`/validation-sessions/${id}/`);
    }

    async createValidationSession(data: {
        draft_summary_id: string;
        sales_rep_email: string;
    }): Promise<AxiosResponse<ValidationSession>> {
        return this.client.post('/validation-sessions/', data);
    }

    async updateValidationSession(
        id: string,
        data: Partial<ValidationFormData>
    ): Promise<AxiosResponse<ValidationSession>> {
        return this.client.patch(`/validation-sessions/${id}/`, data);
    }

    async completeValidationSession(
        id: string,
        data: ValidationFormData
    ): Promise<AxiosResponse<ValidationSession>> {
        return this.client.post(`/validation-sessions/${id}/complete/`, data);
    }

    // Draft summary endpoints
    async getDraftSummary(id: string): Promise<AxiosResponse<DraftSummary>> {
        return this.client.get(`/draft-summaries/${id}/`);
    }

    // CRM sync endpoints
    async getCRMSyncRecords(validationSessionId: string): Promise<AxiosResponse<CRMSyncRecord[]>> {
        return this.client.get(`/validation-sessions/${validationSessionId}/crm-sync-records/`);
    }

    async retryCRMSync(syncRecordId: string): Promise<AxiosResponse<CRMSyncRecord>> {
        return this.client.post(`/crm-sync-records/${syncRecordId}/retry/`);
    }

    // Dashboard endpoints
    async getDashboardStats(): Promise<AxiosResponse<{
        total_meetings: number;
        pending_validations: number;
        completed_validations: number;
        failed_crm_syncs: number;
    }>> {
        return this.client.get('/dashboard/stats/');
    }

    // Meeting dashboard endpoints
    async getMeetingsWithDetails(params?: {
        status?: string;
        validation_status?: string;
        crm_sync_status?: string;
        platform?: string;
        search?: string;
        page?: number;
        limit?: number;
    }): Promise<AxiosResponse<{ results: any[]; count: number }>> {
        return this.client.get('/meetings/with-details/', { params });
    }

    async getMeetingDashboardStats(): Promise<AxiosResponse<{
        total_meetings: number;
        meetings_with_transcripts: number;
        pending_validations: number;
        completed_validations: number;
        successful_crm_syncs: number;
        failed_crm_syncs: number;
    }>> {
        return this.client.get('/meetings/dashboard-stats/');
    }

    async exportMeetingTranscript(meetingId: string): Promise<AxiosResponse<string>> {
        return this.client.get(`/meetings/${meetingId}/export-transcript/`, {
            responseType: 'text',
        });
    }

    async getMeetingTranscriptComparison(meetingId: string): Promise<AxiosResponse<any>> {
        return this.client.get(`/meetings/${meetingId}/transcript-comparison/`);
    }

    // Email Management endpoints
    async createDraftEmail(data: {
        validation_session_id: number;
        email_type: string;
        recipient_email: string;
        recipient_name?: string;
        cc_emails?: string[];
        bcc_emails?: string[];
        custom_template?: string;
        include_meeting_summary?: boolean;
        include_action_items?: boolean;
        include_next_steps?: boolean;
    }): Promise<AxiosResponse<any>> {
        return this.client.post('/meetings/draft-emails/', data);
    }

    async listDraftEmails(params?: {
        status?: string;
        email_type?: string;
        validation_session_id?: number;
    }): Promise<AxiosResponse<any>> {
        return this.client.get('/meetings/draft-emails/list/', { params });
    }

    async getDraftEmail(emailId: number): Promise<AxiosResponse<any>> {
        return this.client.get(`/meetings/draft-emails/${emailId}/`);
    }

    async updateDraftEmail(emailId: number, data: any): Promise<AxiosResponse<any>> {
        return this.client.put(`/meetings/draft-emails/${emailId}/update/`, data);
    }

    async deleteDraftEmail(emailId: number): Promise<AxiosResponse<any>> {
        return this.client.delete(`/meetings/draft-emails/${emailId}/delete/`);
    }

    // Email Approval endpoints
    async requestEmailApproval(data: {
        draft_email_id: number;
        approver_email: string;
        approval_expires_hours?: number;
    }): Promise<AxiosResponse<any>> {
        return this.client.post('/meetings/email-approvals/request/', data);
    }

    async respondToEmailApproval(data: {
        approval_token: string;
        action: 'approve' | 'reject';
        rejection_reason?: string;
    }): Promise<AxiosResponse<any>> {
        return this.client.post('/meetings/email-approvals/respond/', data);
    }

    async listEmailApprovals(params?: {
        status?: string;
        approver_email?: string;
    }): Promise<AxiosResponse<any>> {
        return this.client.get('/meetings/email-approvals/list/', { params });
    }

    // Scheduled Email endpoints
    async scheduleEmail(data: {
        draft_email_id: number;
        scheduled_send_time: string;
    }): Promise<AxiosResponse<any>> {
        return this.client.post('/meetings/scheduled-emails/', data);
    }

    async listScheduledEmails(params?: {
        email_type?: string;
    }): Promise<AxiosResponse<any>> {
        return this.client.get('/meetings/scheduled-emails/list/', { params });
    }

    async cancelScheduledEmail(emailId: number): Promise<AxiosResponse<any>> {
        return this.client.post(`/meetings/scheduled-emails/${emailId}/cancel/`);
    }

    async sendEmailImmediately(emailId: number): Promise<AxiosResponse<any>> {
        return this.client.post(`/meetings/scheduled-emails/${emailId}/send/`);
    }
}

export const apiClient = new ApiClient();
export default apiClient;