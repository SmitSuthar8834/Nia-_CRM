import React from 'react';
import {
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Button,
  Box,
  Chip,
} from '@mui/material';
import { format } from 'date-fns';
import { useNavigate } from 'react-router-dom';

const UpcomingDebriefings = ({ debriefings }) => {
  const navigate = useNavigate();

  const handleStartDebriefing = (meetingId) => {
    navigate(`/debriefing/${meetingId}`);
  };

  return (
    <Paper sx={{ p: 2, height: '400px', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Upcoming Debriefings</Typography>
        <Button size="small" onClick={() => navigate('/debriefing')}>
          View All
        </Button>
      </Box>
      
      {debriefings.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
          <Typography color="text.secondary">No upcoming debriefings</Typography>
        </Box>
      ) : (
        <List sx={{ flex: 1, overflow: 'auto' }}>
          {debriefings.map((debriefing) => (
            <ListItem key={debriefing.id} divider>
              <ListItemText
                primary={debriefing.meeting?.title || 'Meeting Debriefing'}
                secondary={
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Scheduled: {format(new Date(debriefing.scheduled_time), 'MMM dd, yyyy HH:mm')}
                    </Typography>
                    <Chip
                      label={debriefing.status}
                      size="small"
                      color={debriefing.status === 'overdue' ? 'error' : 'warning'}
                      sx={{ mt: 0.5 }}
                    />
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Button
                  size="small"
                  variant="contained"
                  onClick={() => handleStartDebriefing(debriefing.meeting?.id)}
                >
                  Start
                </Button>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
};

export default UpcomingDebriefings;