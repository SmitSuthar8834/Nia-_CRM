import React from 'react';
import {
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Box,
  Button,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  RecordVoiceOver as DebriefingIcon,
  People as ParticipantsIcon,
  TrendingUp as IntelligenceIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

const MeetingCard = ({ meeting, onClick, onStartDebriefing }) => {
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

  const getConfidenceColor = (score) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  return (
    <ListItem
      divider
      sx={{
        cursor: 'pointer',
        '&:hover': {
          backgroundColor: 'action.hover',
        },
      }}
      onClick={onClick}
    >
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <span>{meeting.title}</span>
            {meeting.is_sales_meeting && (
              <Tooltip title="Sales Meeting Detected">
                <IntelligenceIcon color="primary" fontSize="small" />
              </Tooltip>
            )}
          </Box>
        }
        secondary={
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <span>
                {format(new Date(meeting.start_time), 'HH:mm')} - 
                {format(new Date(meeting.end_time), 'HH:mm')}
              </span>
              <Chip
                label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
                size="small"
                color={getMeetingTypeColor(meeting.meeting_type)}
              />
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ParticipantsIcon fontSize="small" color="action" />
              <span>{meeting.participants?.length || 0} participants</span>
              
              {meeting.confidence_score > 0 && (
                <>
                  <Chip
                    label={`${Math.round(meeting.confidence_score * 100)}% confidence`}
                    size="small"
                    color={getConfidenceColor(meeting.confidence_score)}
                    variant="outlined"
                  />
                </>
              )}
            </Box>
          </Box>
        }
      />
      
      <ListItemSecondaryAction>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {!meeting.debriefing_completed && (
            <Button
              size="small"
              variant={meeting.debriefing_scheduled ? 'outlined' : 'contained'}
              startIcon={<DebriefingIcon />}
              onClick={(e) => {
                e.stopPropagation();
                onStartDebriefing();
              }}
              color={meeting.debriefing_scheduled ? 'primary' : 'warning'}
            >
              {meeting.debriefing_scheduled ? 'Continue' : 'Start'} Debriefing
            </Button>
          )}
          
          {meeting.debriefing_completed && (
            <Chip
              label="Debriefing Complete"
              size="small"
              color="success"
            />
          )}
        </Box>
      </ListItemSecondaryAction>
    </ListItem>
  );
};

export default MeetingCard;