import React from 'react';
import {
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Box,
  Button,
} from '@mui/material';
import { format } from 'date-fns';
import { useNavigate } from 'react-router-dom';

const RecentMeetings = ({ meetings }) => {
  const navigate = useNavigate();

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
    <Paper sx={{ p: 2, height: '400px', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Recent Meetings</Typography>
        <Button size="small" onClick={() => navigate('/calendar')}>
          View All
        </Button>
      </Box>
      
      {meetings.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
          <Typography color="text.secondary">No recent meetings</Typography>
        </Box>
      ) : (
        <List sx={{ flex: 1, overflow: 'auto' }}>
          {meetings.map((meeting) => (
            <ListItem key={meeting.id} divider>
              <ListItemText
                primary={meeting.title}
                secondary={
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      {format(new Date(meeting.start_time), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {meeting.participants?.length || 0} participants
                    </Typography>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Chip
                  label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
                  size="small"
                  color={getMeetingTypeColor(meeting.meeting_type)}
                />
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
};

export default RecentMeetings;