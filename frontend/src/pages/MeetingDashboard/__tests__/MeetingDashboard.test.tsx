import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import MeetingDashboard from '../MeetingDashboard';
import apiClient from '../../../services/api';

// Mock the API client
jest.mock('../../../services/api');
const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
    ...jest.requireActual('react-router-dom'),
    useNavigate: () => mockNavigate,
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

const mockMeetingsResponse = {
    data: {
        results: [
            {
                id: '1',
                meeting_url: 'https://meet.google.com/test',
                platform: 'meet',
                title: 'Sales Call with Acme Corp',
                start_time: '2024-01-15T10:00:00Z',
                end_time: '2024-01-15T11:00:00Z',
                attendees: ['john@example.com', 'jane@acme.com'],
                status: 'completed',
                created_at: '2024-01-15T09:00:00Z',
                validation_session: {
                    id: 'vs1',
                    validation_status: 'completed',
                    draft_summary: 'ds1',
                    sales_rep_email: 'john@example.com',
                    validation_questions: [],
                    rep_responses: {},
                    validated_summary: 'Meeting completed successfully',
                    approved_crm_updates: {},
                    started_at: '2024-01-15T11:05:00Z',
                    completed_at: '2024-01-15T11:15:00Z',
                },
                crm_sync_records: [
                    {
                        id: 'csr1',
                        validation_session: 'vs1',
                        crm_system: 'salesforce',
                        sync_status: 'completed',
                        crm_record_id: 'sf123',
                        sync_payload: {},
                        synced_at: '2024-01-15T11:20:00Z',
                    },
                ],
                has_transcript: true,
            },
        ],
        count: 1,
    },
};

const mockStatsResponse = {
    data: {
        total_meetings: 25,
        meetings_with_transcripts: 20,
        pending_validations: 5,
        completed_validations: 15,
        successful_crm_syncs: 12,
        failed_crm_syncs: 2,
    },
};

describe('MeetingDashboard', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockedApiClient.getMeetingsWithDetails.mockResolvedValue(mockMeetingsResponse);
        mockedApiClient.getMeetingDashboardStats.mockResolvedValue(mockStatsResponse);
    });

    it('renders meeting dashboard with loading state', () => {
        renderWithProviders(<MeetingDashboard />);
        expect(screen.getByText('Loading meeting dashboard...')).toBeInTheDocument();
    });

    it('renders meeting dashboard with stats cards after loading', async () => {
        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Meeting Dashboard')).toBeInTheDocument();
            expect(screen.getByText('Total Meetings')).toBeInTheDocument();
            expect(screen.getByText('25')).toBeInTheDocument();
        });
    });

    it('displays meetings in table format', async () => {
        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Sales Call with Acme Corp')).toBeInTheDocument();
            expect(screen.getByText('MEET')).toBeInTheDocument();
        });
    });

    it('handles search functionality', async () => {
        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByPlaceholderText('Search meeting content...')).toBeInTheDocument();
        });

        const searchInput = screen.getByPlaceholderText('Search meeting content...');
        fireEvent.change(searchInput, { target: { value: 'Acme' } });

        // Wait for debounced search
        await waitFor(() => {
            expect(mockedApiClient.getMeetingsWithDetails).toHaveBeenCalledWith(
                expect.objectContaining({
                    search: 'Acme',
                })
            );
        });
    });

    it('handles refresh button click', async () => {
        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Refresh')).toBeInTheDocument();
        });

        const refreshButton = screen.getByText('Refresh');
        fireEvent.click(refreshButton);

        await waitFor(() => {
            expect(mockedApiClient.getMeetingsWithDetails).toHaveBeenCalledTimes(3);
        });
    });

    it('displays error message when API calls fail', async () => {
        const errorMessage = 'Failed to load meeting data';
        mockedApiClient.getMeetingsWithDetails.mockRejectedValue({
            response: { data: { message: errorMessage } },
        });

        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });
    });

    it('displays no meetings message when no results', async () => {
        mockedApiClient.getMeetingsWithDetails.mockResolvedValue({
            data: { results: [], count: 0 },
        });

        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByText('No meetings found')).toBeInTheDocument();
        });
    });

    it('shows correct filter options', async () => {
        renderWithProviders(<MeetingDashboard />);

        await waitFor(() => {
            expect(screen.getByLabelText('Meeting Status')).toBeInTheDocument();
            expect(screen.getByLabelText('Validation Status')).toBeInTheDocument();
            expect(screen.getByLabelText('CRM Sync Status')).toBeInTheDocument();
            expect(screen.getByLabelText('Platform')).toBeInTheDocument();
        });
    });
});