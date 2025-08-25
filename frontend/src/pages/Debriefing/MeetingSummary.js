import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
} from '@mui/material';
import {
  Person as PersonIcon,
  Business as BusinessIcon,
  CalendarToday as CalendarIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

const MeetingSummary = ({ meeting }) => {
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

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Meeting Summary
      </Typography>
      
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          {meeting.title}
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <CalendarIcon fontSize="small" color="action" />
          <Typography variant="body2" color="text.secondary">
            {format(new Date(meeting.start_time), 'MMMM dd, yyyy')}
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <ScheduleIcon fontSize="small" color="action" />
          <Typography variant="body2" color="text.secondary">
            {format(new Date(meeting.start_time), 'HH:mm')} - 
            {format(new Date(meeting.end_time), 'HH:mm')}
          </Typography>
        </Box>
        
        <Chip
          label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
          color={getMeetingTypeColor(meeting.meeting_type)}
          size="small"
          sx={{ mb: 1 }}
        />
        
        {meeting.is_sales_meeting && (
          <Box>
            <Chip
              label={`Sales Meeting (${Math.round(meeting.confidence_score * 100)}% confidence)`}
              color="success"
              size="small"
              variant="outlined"
            />
          </Box>
        )}
      </Box>

      <Divider sx={{ my: 2 }} />

      <Typography variant="subtitle2" gutterBottom>
        Participants ({meeting.participants?.length || 0})
      </Typography>
      
      {meeting.participants?.length > 0 ? (
        <List dense>
          {meeting.participants.map((participant, index) => (
            <ListItem key={index} sx={{ px: 0 }}>
              <ListItemAvatar>
                <Avatar sx={{ width: 32, height: 32 }}>
                  {participant.is_external ? <BusinessIcon /> : <PersonIcon />}
                </Avatar>
              </ListItemAvatar>
              <ListItemText
                primary={
                  <Typography variant="body2">
                    {participant.name || participant.email}
                  </Typography>
                }
                secondary={
                  <Box>
                    {participant.company && (
                      <Typography variant="caption" display="block">
                        {participant.company}
                      </Typography>
                    )}
                    {participant.matched_lead && (
                      <Chip
                        label="Matched Lead"
                        size="small"
                        color="success"
                        variant="outlined"
                        sx={{ mt: 0.5, height: 16, fontSize: '0.6rem' }}
                      />
                    )}
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No participants found
        </Typography>
      )}
    </Paper>
  );
};

export default MeetingSummary;