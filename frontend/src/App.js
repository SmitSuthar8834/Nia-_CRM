import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/Layout/Layout';
import Login from './pages/Login/Login';
import Dashboard from './pages/Dashboard/Dashboard';
import MeetingCalendar from './pages/MeetingCalendar/MeetingCalendar';
import Debriefing from './pages/Debriefing/Debriefing';
import LeadManagement from './pages/LeadManagement/LeadManagement';
import CompetitiveIntelligence from './pages/CompetitiveIntelligence/CompetitiveIntelligence';
import ActionItems from './pages/ActionItems/ActionItems';
import Settings from './pages/Settings/Settings';
import ValidationDashboard from './pages/ValidationDashboard/ValidationDashboard';
import ValidationSession from './pages/ValidationSession/ValidationSession';
import MeetingDashboard from './pages/MeetingDashboard/MeetingDashboard';
import TranscriptComparison from './pages/TranscriptComparison/TranscriptComparison';
import LoadingSpinner from './components/Common/LoadingSpinner';

function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Box sx={{ display: 'flex' }}>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/calendar" element={<MeetingCalendar />} />
          <Route path="/debriefing/:meetingId?" element={<Debriefing />} />
          <Route path="/leads" element={<LeadManagement />} />
          <Route path="/competitive-intelligence" element={<CompetitiveIntelligence />} />
          <Route path="/action-items" element={<ActionItems />} />
          <Route path="/validation" element={<ValidationDashboard />} />
          <Route path="/validation/:sessionId" element={<ValidationSession />} />
          <Route path="/meetings" element={<MeetingDashboard />} />
          <Route path="/meetings/:meetingId/transcript-comparison" element={<TranscriptComparison />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    </Box>
  );
}

export default App;