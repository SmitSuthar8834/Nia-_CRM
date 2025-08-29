import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ValidationSession from '../ValidationSession';
import apiClient from '../../../services/api';

// Mock the API client
jest.mock('../../../services/api');
const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
    ...jest.requireActual('react-router-dom'),
    useNavigate: () => mockNavigate,
    useParams: () => ({ sessionId: 'test-session-id' }),
}));

const theme = createTheme();

const renderWithProviders = (component: React.ReactElement) => {
    return render(
        <BrowserRouter>
            <ThemeProvider theme={theme}>
                {component}
            </ThemeProvider>
        </BrowserRouter>
    );
};

describe('ValidationSession', () => {
    const mockSession = {
        id: 'test-session-id',
        draft_summary: 'draft-summary-id',
        sales_rep_email: 'rep@example.com',
        validation_questions: [],
        rep_responses: {},
        validated_summary: '',
        approved_crm_updates: {},
        validation_status: 'pending' as const,
        started_at: '2024-01-01T10:00:00Z',
        completed_at: null,
    };

    const mockDraftSummary = {
        id: 'draft-summary-id',
        bot_session: 'bot-session-id',
        ai_generated_summary: 'This is an AI generated summary of the meeting.',
        extracted_action_items: [
            {
                id: '1',
                description: 'Follow up with client',
                assignee: 'rep@example.com',
                status: 'pending' as const,
            },
        ],
        suggested_next_steps: 'Schedule follow-up call',
        suggested_crm_updates: { stage: 'qualified' },
        confidence_score: 0.85,
        created_at: '2024-01-01T10:05:00Z',
    };

    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders loading state initially', () => {
        mockedApiClient.getValidationSession.mockImplementation(() =>
            new Promise(() => { }) // Never resolves to keep loading state
        );

        renderWithProviders(<ValidationSession />);

        expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('renders validation session with draft summary', async () => {
        mockedApiClient.getValidationSession.mockResolvedValue({
            data: mockSession,
        } as any);
        mockedApiClient.getDraftSummary.mockResolvedValue({
            data: mockDraftSummary,
        } as any);

        renderWithProviders(<ValidationSession />);

        await waitFor(() => {
            expect(screen.getByText('Validation Session')).toBeInTheDocument();
        });

        // Check AI generated summary
        expect(screen.getByText('AI Generated Summary')).toBeInTheDocument();
        expect(screen.getByText('This is an AI generated summary of the meeting.')).toBeInTheDocument();
        expect(screen.getByText('Confidence Score: 85.0%')).toBeInTheDocument();

        // Check action items
        expect(screen.getByText('Action Items:')).toBeInTheDocument();
        expect(screen.getByText('Follow up with client')).toBeInTheDocument();

        // Check validation form
        expect(screen.getByText('Validation & Feedback')).toBeInTheDocument();
        expect(screen.getByLabelText('Summary is accurate')).toBeInTheDocument();
        expect(screen.getByLabelText('Next steps and timeline')).toBeInTheDocument();
    });

    it('handles form submission for completing validation', async () => {
        mockedApiClient.getValidationSession.mockResolvedValue({
            data: mockSession,
        } as any);
        mockedApiClient.getDraftSummary.mockResolvedValue({
            data: mockDraftSummary,
        } as any);
        mockedApiClient.completeValidationSession.mockResolvedValue({
            data: { ...mockSession, validation_status: 'completed' },
        } as any);

        renderWithProviders(<ValidationSession />);

        await waitFor(() => {
            expect(screen.getByText('Validation Session')).toBeInTheDocument();
        });

        // Fill in required fields
        const nextStepsField = screen.getByLabelText('Next steps and timeline');
        fireEvent.change(nextStepsField, { target: { value: 'Schedule follow-up call next week' } });

        // Check summary approval
        const summaryCheckbox = screen.getByLabelText('Summary is accurate');
        fireEvent.click(summaryCheckbox);

        // Submit the form
        const completeButton = screen.getByText('Complete Validation');
        fireEvent.click(completeButton);

        await waitFor(() => {
            expect(mockedApiClient.completeValidationSession).toHaveBeenCalledWith(
                'test-session-id',
                expect.objectContaining({
                    summary_approved: true,
                    next_steps: 'Schedule follow-up call next week',
                })
            );
        });
    });

    it('shows summary edits field when summary is not approved', async () => {
        mockedApiClient.getValidationSession.mockResolvedValue({
            data: mockSession,
        } as any);
        mockedApiClient.getDraftSummary.mockResolvedValue({
            data: mockDraftSummary,
        } as any);

        renderWithProviders(<ValidationSession />);

        await waitFor(() => {
            expect(screen.getByText('Validation Session')).toBeInTheDocument();
        });

        // Initially, summary edits field should not be visible
        expect(screen.queryByLabelText('Summary corrections/edits')).not.toBeInTheDocument();

        // Uncheck summary approval (it should be unchecked by default, but let's be explicit)
        const summaryCheckbox = screen.getByLabelText('Summary is accurate');
        expect(summaryCheckbox).not.toBeChecked();

        // Summary edits field should now be visible
        expect(screen.getByLabelText('Summary corrections/edits')).toBeInTheDocument();
    });

    it('handles API errors gracefully', async () => {
        mockedApiClient.getValidationSession.mockRejectedValue(
            new Error('Session not found')
        );

        renderWithProviders(<ValidationSession />);

        await waitFor(() => {
            expect(screen.getByText('Validation session not found')).toBeInTheDocument();
        });
    });

    it('disables form when session is completed', async () => {
        const completedSession = {
            ...mockSession,
            validation_status: 'completed' as const,
            completed_at: '2024-01-01T11:00:00Z',
        };

        mockedApiClient.getValidationSession.mockResolvedValue({
            data: completedSession,
        } as any);
        mockedApiClient.getDraftSummary.mockResolvedValue({
            data: mockDraftSummary,
        } as any);

        renderWithProviders(<ValidationSession />);

        await waitFor(() => {
            expect(screen.getByText('Validation Session')).toBeInTheDocument();
        });

        // Form fields should be disabled
        expect(screen.getByLabelText('Summary is accurate')).toBeDisabled();
        expect(screen.getByLabelText('Next steps and timeline')).toBeDisabled();

        // Action buttons should not be present
        expect(screen.queryByText('Complete Validation')).not.toBeInTheDocument();
        expect(screen.queryByText('Save Progress')).not.toBeInTheDocument();
    });
});