import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ValidationDashboard from '../ValidationDashboard';
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

describe('ValidationDashboard', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders loading state initially', () => {
        mockedApiClient.getValidationSessions.mockImplementation(() =>
            new Promise(() => { }) // Never resolves to keep loading state
        );
        mockedApiClient.getDashboardStats.mockImplementation(() =>
            new Promise(() => { }) // Never resolves to keep loading state
        );

        renderWithProviders(<ValidationDashboard />);

        expect(screen.getByText('Loading validation dashboard...')).toBeInTheDocument();
    });

    it('renders dashboard with stats and sessions', async () => {
        const mockStats = {
            total_meetings: 10,
            pending_validations: 3,
            completed_validations: 7,
            failed_crm_syncs: 1,
        };

        const mockSessions = [
            {
                id: '1',
                draft_summary: 'summary-1',
                sales_rep_email: 'rep@example.com',
                validation_questions: [],
                rep_responses: {},
                validated_summary: '',
                approved_crm_updates: {},
                validation_status: 'pending' as const,
                started_at: '2024-01-01T10:00:00Z',
                completed_at: null,
            },
        ];

        mockedApiClient.getValidationSessions.mockResolvedValue({
            data: { results: mockSessions, count: 1 },
        } as any);
        mockedApiClient.getDashboardStats.mockResolvedValue({
            data: mockStats,
        } as any);

        renderWithProviders(<ValidationDashboard />);

        await waitFor(() => {
            expect(screen.getByText('Validation Dashboard')).toBeInTheDocument();
        });

        // Check stats cards
        expect(screen.getByText('Total Meetings')).toBeInTheDocument();
        expect(screen.getByText('10')).toBeInTheDocument();
        expect(screen.getByText('Pending Validations')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();

        // Check sessions table
        expect(screen.getByText('rep@example.com')).toBeInTheDocument();
        expect(screen.getByText('pending')).toBeInTheDocument();
    });

    it('handles API errors gracefully', async () => {
        mockedApiClient.getValidationSessions.mockRejectedValue(
            new Error('API Error')
        );
        mockedApiClient.getDashboardStats.mockRejectedValue(
            new Error('API Error')
        );

        renderWithProviders(<ValidationDashboard />);

        await waitFor(() => {
            expect(screen.getByText(/Failed to load validation data/)).toBeInTheDocument();
        });
    });

    it('filters sessions by search term', async () => {
        const mockSessions = [
            {
                id: '1',
                draft_summary: 'summary-1',
                sales_rep_email: 'alice@example.com',
                validation_questions: [],
                rep_responses: {},
                validated_summary: '',
                approved_crm_updates: {},
                validation_status: 'pending' as const,
                started_at: '2024-01-01T10:00:00Z',
                completed_at: null,
            },
            {
                id: '2',
                draft_summary: 'summary-2',
                sales_rep_email: 'bob@example.com',
                validation_questions: [],
                rep_responses: {},
                validated_summary: '',
                approved_crm_updates: {},
                validation_status: 'completed' as const,
                started_at: '2024-01-01T11:00:00Z',
                completed_at: '2024-01-01T11:30:00Z',
            },
        ];

        mockedApiClient.getValidationSessions.mockResolvedValue({
            data: { results: mockSessions, count: 2 },
        } as any);
        mockedApiClient.getDashboardStats.mockResolvedValue({
            data: {
                total_meetings: 2,
                pending_validations: 1,
                completed_validations: 1,
                failed_crm_syncs: 0,
            },
        } as any);

        renderWithProviders(<ValidationDashboard />);

        await waitFor(() => {
            expect(screen.getByText('alice@example.com')).toBeInTheDocument();
            expect(screen.getByText('bob@example.com')).toBeInTheDocument();
        });
    });
});