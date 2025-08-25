import React from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
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
  Email as EmailIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

const MeetingDetails = ({ meeting, onClose, onStartDebriefing }) => {
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
    <>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">{meeting.title}</Typography>
          <Chip
            label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
            color={getMeetingTypeColor(meeting.meeting_type)}
          />
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Meeting Information
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Date:</strong> {format(new Date(meeting.start_time), 'MMMM dd, yyyy')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Time:</strong> {format(new Date(meeting.start_time), 'HH:mm')} - 
            {format(new Date(meeting.end_time), 'HH:mm')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Organizer:</strong> {meeting.organizer?.email || 'Unknown'}
          </Typography>
          
          {meeting.is_sales_meeting && (
            <Box sx={{ mt: 1 }}>
              <Chip
                label={`Sales Meeting (${Math.round(meeting.confidence_score * 100)}% confidence)`}
                color="primary"
                size="small"
              />
            </Box>
          )}
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Participants ({meeting.participants?.length || 0})
          </Typography>
          
          {meeting.participants?.length > 0 ? (
            <List dense>
              {meeting.participants.map((participant, index) => (
                <ListItem key={index}>
                  <ListItemAvatar>
                    <Avatar>
                      {participant.is_external ? <BusinessIcon /> : <PersonIcon />}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={participant.name || participant.email}
                    secondary={
                      <Box>
                        {participant.email && (
                          <Typography variant="caption" display="block">
                            <EmailIcon fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
                            {participant.email}
                          </Typography>
                        )}
                        {participant.company && (
                          <Typography variant="caption" display="block">
                            <BusinessIcon fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
                            {participant.company}
                          </Typography>
                        )}
                        {participant.matched_lead && (
                          <Chip
                            label={`Matched Lead (${Math.round(participant.match_confidence * 100)}%)`}
                            size="small"
                            color="success"
                            variant="outlined"
                            sx={{ mt: 0.5 }}
                          />
                        )}
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          ) : (
            <Typography color="text.secondary">No participants found</Typography>
          )}
        </Box>

        {meeting.debriefing_completed && (
          <>
            <Divider sx={{ my: 2 }} />
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                Debriefing Status
              </Typography>
              <Chip
                label="Debriefing Completed"
                color="success"
                sx={{ mb: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                Meeting insights have been captured and processed.
              </Typography>
            </Box>
          </>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        {!meeting.debriefing_completed && (
          <Button
            variant="contained"
            onClick={onStartDebriefing}
            color={meeting.debriefing_scheduled ? 'primary' : 'warning'}
          >
            {meeting.debriefing_scheduled ? 'Continue' : 'Start'} Debriefing
          </Button>
        )}
      </DialogActions>
    </>
  );
};

export default MeetingDetails;