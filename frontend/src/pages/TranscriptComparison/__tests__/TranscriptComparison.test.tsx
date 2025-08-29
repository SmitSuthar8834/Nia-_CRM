import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import TranscriptComparison from '../TranscriptComparison';
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

const renderWithProviders = (component: React.ReactElement, initialEntries = ['/meetings/1/transcript-comparison']) => {
    return render(
        <MemoryRouter initialEntries={initialEntries}>
            <ThemeProvider theme={theme}>
                {component}
            </ThemeProvider>
        </MemoryRouter>
    );
};

describe('TranscriptComparison', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockedApiClient.getMeetingTranscriptComparison.mockResolvedValue({
            data: {
                meeting: {
                    id: '1',
                    title: 'Test Meeting',
                    platform: 'meet',
                    start_time: '2024-01-15T10:00:00Z',
                    end_time: '2024-01-15T11:00:00Z',
                    attendees: [],
                    status: 'completed',
                    created_at: '2024-01-15T09:00:00Z',
                    meeting_url: 'https://meet.google.com/test',
                },
                rawTranscript: 'Test transcript',
                validatedTranscript: 'Validated transcript',
            },
        });
    });

    it('renders transcript comparison with loading state', () => {
        renderWithProviders(<TranscriptComparison />);
        expect(screen.getByText('Loading transcript comparison...')).toBeInTheDocument();
    });

    it('renders component without crashing', () => {
        const { container } = renderWithProviders(<TranscriptComparison />);
        expect(container).toBeInTheDocument();
    });
});