import React, { useState, useEffect } from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Grid,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
  Tab,
  Tabs,
  Paper,
} from '@mui/material';
import {
  Person as PersonIcon,
  Business as BusinessIcon,
  Email as EmailIcon,
  Phone as PhoneIcon,
  CalendarToday as CalendarIcon,
  TrendingUp as ScoreIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { toast } from 'react-toastify';
import { format } from 'date-fns';

const LeadDetails = ({ lead, onClose, onUpdate }) => {
  const [tabValue, setTabValue] = useState(0);
  const [meetings, setMeetings] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tabValue === 1) {
      fetchMeetings();
    } else if (tabValue === 2) {
      fetchActivities();
    }
  }, [tabValue, lead.id]);

  const fetchMeetings = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/v1/leads/${lead.id}/meetings/`);
      setMeetings(response.data.results || []);
    } catch (error) {
      console.error('Failed to fetch meetings:', error);
      toast.error('Failed to load meetings');
    } finally {
      setLoading(false);
    }
  };

  const fetchActivities = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/v1/leads/${lead.id}/activities/`);
      setActivities(response.data.results || []);
    } catch (error) {
      console.error('Failed to fetch activities:', error);
      toast.error('Failed to load activities');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'info',
      qualified: 'success',
      unqualified: 'error',
      contacted: 'warning',
      converted: 'primary',
    };
    return colors[status] || 'default';
  };

  const getQualificationScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  const getMeetingTypeColor = (type) => {
    const colors = {
      discovery: 'primary',
      demo: 'secondary',
      negotiation: 'warning',
      follow_up: 'info',
      internal: 'default',
    };
    return colors[type] || 'default';
  };

  const renderOverview = () => (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            Contact Information
          </Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <PersonIcon fontSize="small" color="action" />
            <Typography>
              {lead.first_name} {lead.last_name}
            </Typography>
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <EmailIcon fontSize="small" color="action" />
            <Typography>{lead.email}</Typography>
          </Box>
          
          {lead.phone && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <PhoneIcon fontSize="small" color="action" />
              <Typography>{lead.phone}</Typography>
            </Box>
          )}
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <BusinessIcon fontSize="small" color="action" />
            <Typography>{lead.company}</Typography>
          </Box>
          
          {lead.title && (
            <Typography variant="body2" color="text.secondary">
              {lead.title}
            </Typography>
          )}
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            Lead Status
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <Chip
              label={lead.status}
              color={getStatusColor(lead.status)}
              sx={{ mb: 1, mr: 1 }}
            />
            <Chip
              label={lead.source}
              variant="outlined"
              sx={{ mb: 1 }}
            />
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <ScoreIcon fontSize="small" color="action" />
            <Typography>Qualification Score:</Typography>
            <Chip
              label={`${lead.qualification_score}%`}
              color={getQualificationScoreColor(lead.qualification_score)}
              size="small"
            />
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <CalendarIcon fontSize="small" color="action" />
            <Typography>
              {lead.meeting_count} meetings
            </Typography>
          </Box>
          
          {lead.last_meeting_date && (
            <Typography variant="body2" color="text.secondary">
              Last meeting: {format(new Date(lead.last_meeting_date), 'MMM dd, yyyy')}
            </Typography>
          )}
          
          {lead.relationship_stage && (
            <Typography variant="body2" color="text.secondary">
              Relationship stage: {lead.relationship_stage}
            </Typography>
          )}
        </Grid>
      </Grid>
    </Box>
  );

  const renderMeetings = () => (
    <Box>
      {loading ? (
        <Typography>Loading meetings...</Typography>
      ) : meetings.length === 0 ? (
        <Typography color="text.secondary">No meetings found</Typography>
      ) : (
        <List>
          {meetings.map((meeting) => (
            <ListItem key={meeting.id} divider>
              <ListItemText
                primary={meeting.title}
                secondary={
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      {format(new Date(meeting.start_time), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                      <Chip
                        label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
                        size="small"
                        color={getMeetingTypeColor(meeting.meeting_type)}
                      />
                      {meeting.debriefing_completed && (
                        <Chip
                          label="Debriefed"
                          size="small"
                          color="success"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );

  const renderActivities = () => (
    <Box>
      {loading ? (
        <Typography>Loading activities...</Typography>
      ) : activities.length === 0 ? (
        <Typography color="text.secondary">No activities found</Typography>
      ) : (
        <List>
          {activities.map((activity) => (
            <ListItem key={activity.id} divider>
              <ListItemText
                primary={activity.title}
                secondary={
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      {activity.description}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {format(new Date(activity.created_at), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );

  return (
    <>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            {lead.first_name} {lead.last_name}
          </Typography>
          <Typography variant="subtitle2" color="text.secondary">
            {lead.company}
          </Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Paper sx={{ width: '100%' }}>
          <Tabs
            value={tabValue}
            onChange={(e, newValue) => setTabValue(newValue)}
            indicatorColor="primary"
            textColor="primary"
          >
            <Tab label="Overview" />
            <Tab label={`Meetings (${lead.meeting_count})`} />
            <Tab label="Activities" />
          </Tabs>
          
          <Box sx={{ p: 3 }}>
            {tabValue === 0 && renderOverview()}
            {tabValue === 1 && renderMeetings()}
            {tabValue === 2 && renderActivities()}
          </Box>
        </Paper>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button variant="contained" onClick={() => {/* TODO: Edit lead */}}>
          Edit Lead
        </Button>
      </DialogActions>
    </>
  );
};

export default LeadDetails;