import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Chip,
  Button,
} from '@mui/material';
import {
  CalendarToday as CalendarIcon,
  People as PeopleIcon,
  TrendingUp as TrendingIcon,
  Assignment as AssignmentIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';
import MetricCard from './MetricCard';
import RecentMeetings from './RecentMeetings';
import UpcomingDebriefings from './UpcomingDebriefings';
import ActionItemsSummary from './ActionItemsSummary';

const Dashboard = () => {
  const [metrics, setMetrics] = useState({
    totalMeetings: 0,
    completedDebriefings: 0,
    activeLeads: 0,
    pendingActions: 0,
  });
  const [recentMeetings, setRecentMeetings] = useState([]);
  const [upcomingDebriefings, setUpcomingDebriefings] = useState([]);
  const [actionItems, setActionItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [metricsRes, meetingsRes, debriefingsRes, actionsRes] = await Promise.all([
        axios.get('/api/v1/analytics/dashboard-metrics/'),
        axios.get('/api/v1/meetings/?limit=5&ordering=-start_time'),
        axios.get('/api/v1/debriefings/?status=scheduled&limit=5'),
        axios.get('/api/v1/action-items/?status=pending&limit=5'),
      ]);

      setMetrics(metricsRes.data);
      setRecentMeetings(meetingsRes.data.results || []);
      setUpcomingDebriefings(debriefingsRes.data.results || []);
      setActionItems(actionsRes.data.results || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const metricCards = [
    {
      title: 'Total Meetings',
      value: metrics.totalMeetings,
      icon: <CalendarIcon />,
      color: 'primary',
      onClick: () => navigate('/calendar'),
    },
    {
      title: 'Completed Debriefings',
      value: metrics.completedDebriefings,
      icon: <PeopleIcon />,
      color: 'success',
      onClick: () => navigate('/debriefing'),
    },
    {
      title: 'Active Leads',
      value: metrics.activeLeads,
      icon: <TrendingIcon />,
      color: 'info',
      onClick: () => navigate('/leads'),
    },
    {
      title: 'Pending Actions',
      value: metrics.pendingActions,
      icon: <AssignmentIcon />,
      color: 'warning',
      onClick: () => navigate('/action-items'),
    },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <Typography>Loading dashboard...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        {/* Metric Cards */}
        {metricCards.map((metric, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <MetricCard {...metric} />
          </Grid>
        ))}
        
        {/* Recent Meetings */}
        <Grid item xs={12} md={6}>
          <RecentMeetings meetings={recentMeetings} />
        </Grid>
        
        {/* Upcoming Debriefings */}
        <Grid item xs={12} md={6}>
          <UpcomingDebriefings debriefings={upcomingDebriefings} />
        </Grid>
        
        {/* Action Items Summary */}
        <Grid item xs={12}>
          <ActionItemsSummary actionItems={actionItems} />
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;