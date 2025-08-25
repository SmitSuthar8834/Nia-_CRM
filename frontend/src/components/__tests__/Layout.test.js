import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Layout from '../Layout/Layout';
import { AuthProvider } from '../../contexts/AuthContext';
import { WebSocketProvider } from '../../contexts/WebSocketContext';

const theme = createTheme();

const MockProviders = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      <AuthProvider>
        <WebSocketProvider>
          {children}
        </WebSocketProvider>
      </AuthProvider>
    </ThemeProvider>
  </BrowserRouter>
);

// Mock the auth context
jest.mock('../../contexts/AuthContext', () => ({
  ...jest.requireActual('../../contexts/AuthContext'),
  useAuth: () => ({
    user: { first_name: 'Test', email: 'test@example.com' },
    logout: jest.fn(),
  }),
}));

// Mock the websocket context
jest.mock('../../contexts/WebSocketContext', () => ({
  ...jest.requireActual('../../contexts/WebSocketContext'),
  useWebSocket: () => ({
    notifications: [],
    joinDebriefingRoom: jest.fn(),
    leaveDebriefingRoom: jest.fn(),
  }),
}));

describe('Layout Component', () => {
  test('renders navigation items', () => {
    render(
      <MockProviders>
        <Layout>
          <div>Test Content</div>
        </Layout>
      </MockProviders>
    );

    expect(screen.getByText('NIA CRM')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Meeting Calendar')).toBeInTheDocument();
    expect(screen.getByText('Debriefing')).toBeInTheDocument();
    expect(screen.getByText('Lead Management')).toBeInTheDocument();
    expect(screen.getByText('Competitive Intel')).toBeInTheDocument();
    expect(screen.getByText('Action Items')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  test('renders children content', () => {
    render(
      <MockProviders>
        <Layout>
          <div>Test Content</div>
        </Layout>
      </MockProviders>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});