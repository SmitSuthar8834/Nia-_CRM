export interface Meeting {
    id: string;
    meeting_url: string;
    platform: 'meet' | 'teams' | 'zoom';
    title: string;
    start_time: string;
    end_time: string;
    attendees: string[];
    status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
    created_at: string;
}

export interface CallBotSession {
    id: string;
    meeting: string;
    bot_session_id: string;
    join_time: string;
    leave_time?: string;
    connection_status: 'connecting' | 'connected' | 'disconnected' | 'failed';
    raw_transcript: string;
    speaker_mapping: Record<string, string>;
}

export interface DraftSummary {
    id: string;
    bot_session: string;
    ai_generated_summary: string;
    extracted_action_items: ActionItem[];
    suggested_next_steps: string;
    suggested_crm_updates: Record<string, any>;
    confidence_score: number;
    created_at: string;
}

export interface ActionItem {
    id: string;
    description: string;
    assignee: string;
    due_date?: string;
    status: 'pending' | 'in_progress' | 'completed';
}

export interface ValidationSession {
    id: string;
    draft_summary: string;
    sales_rep_email: string;
    validation_questions: ValidationQuestion[];
    rep_responses: Record<string, any>;
    validated_summary: string;
    approved_crm_updates: Record<string, any>;
    validation_status: 'pending' | 'in_progress' | 'completed' | 'rejected';
    started_at: string;
    completed_at?: string;
}

export interface ValidationQuestion {
    id: string;
    question: string;
    type: 'text' | 'boolean' | 'multiple_choice' | 'rating' | 'confirmation' | 'text_editing';
    options?: string[];
    required: boolean;
    defaultValue?: any;
    helperText?: string;
    validation?: {
        minLength?: number;
        maxLength?: number;
        pattern?: string;
    };
}

export interface CRMSyncRecord {
    id: string;
    validation_session: string;
    crm_system: 'salesforce' | 'hubspot' | 'creatio';
    sync_status: 'pending' | 'in_progress' | 'completed' | 'failed';
    crm_record_id: string;
    sync_payload: Record<string, any>;
    error_message?: string;
    synced_at?: string;
}

export interface ValidationFormData {
    summary_approved: boolean;
    summary_edits?: string;
    next_steps: string;
    crm_updates_approved: boolean;
    crm_updates_edits?: Record<string, any>;
    additional_notes?: string;
    question_responses?: Record<string, any>;
}