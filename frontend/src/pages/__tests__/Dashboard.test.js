import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard/Dashboard';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios;

// Mock react-router-dom
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
}));

// Mock recharts
jest.mock('recharts', () => ({
  PieChart: () => <div data-testid="pie-chart" />,
  Pie: () => <div />,
  Cell: () => <div />,
  BarChart: () => <div data-testid="bar-chart" />,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
}));

const mockDashboardData = {
  metrics: {
    totalMeetings: 25,
    completedDebriefings: 18,
    activeLeads: 42,
    pendingActions: 7,
  },
  meetings: {
    results: [
      {
        id: '1',
        title: 'Test Meeting',
        start_time: '2024-01-15T10:00:00Z',
        meeting_type: 'discovery',
        participants: [{ id: '1', name: 'John Doe' }],
      },
    ],
  },
  debriefings: {
    results: [
      {
        id: '1',
        meeting: { id: '1', title: 'Test Meeting' },
        scheduled_time: '2024-01-15T11:00:00Z',
        status: 'scheduled',
      },
    ],
  },
  actions: {
    results: [
      {
        id: '1',
        description: 'Follow up with client',
        owner: 'John Doe',
        priority: 'high',
        due_date: '2024-01-20',
      },
    ],
  },
};

describe('Dashboard Component', () => {
  beforeEach(() => {
    mockedAxios.get.mockImplementation((url) => {
      if (url.includes('dashboard-metrics')) {
        return Promise.resolve({ data: mockDashboardData.metrics });
      }
      if (url.includes('meetings')) {
        return Promise.resolve({ data: mockDashboardData.meetings });
      }
      if (url.includes('debriefings')) {
        return Promise.resolve({ data: mockDashboardData.debriefings });
      }
      if (url.includes('action-items')) {
        return Promise.resolve({ data: mockDashboardData.actions });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders dashboard title', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  test('displays metric cards with correct values', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('25')).toBeInTheDocument(); // Total Meetings
      expect(screen.getByText('18')).toBeInTheDocument(); // Completed Debriefings
      expect(screen.getByText('42')).toBeInTheDocument(); // Active Leads
      expect(screen.getByText('7')).toBeInTheDocument(); // Pending Actions
    });
  });

  test('displays recent meetings section', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Recent Meetings')).toBeInTheDocument();
      expect(screen.getByText('Test Meeting')).toBeInTheDocument();
    });
  });

  test('displays upcoming debriefings section', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Upcoming Debriefings')).toBeInTheDocument();
    });
  });

  test('displays action items summary', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Pending Action Items')).toBeInTheDocument();
      expect(screen.getByText('Follow up with client')).toBeInTheDocument();
    });
  });
});