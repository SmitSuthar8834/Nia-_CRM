import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Button,
  List,
  ListItem,
  ListItemText,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useWebSocket } from '../../contexts/WebSocketContext';
import DebriefingChat from './DebriefingChat';
import MeetingSummary from './MeetingSummary';
import ExtractedDataPreview from './ExtractedDataPreview';

const Debriefing = () => {
  const { meetingId } = useParams();
  const navigate = useNavigate();
  const { joinDebriefingRoom, leaveDebriefingRoom } = useWebSocket();
  
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [debriefingSession, setDebriefingSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectMeetingOpen, setSelectMeetingOpen] = useState(false);

  useEffect(() => {
    if (meetingId) {
      fetchMeetingAndSession(meetingId);
    } else {
      fetchPendingMeetings();
    }
  }, [meetingId]);

  useEffect(() => {
    if (selectedMeeting && debriefingSession) {
      joinDebriefingRoom(selectedMeeting.id);
      return () => {
        leaveDebriefingRoom(selectedMeeting.id);
      };
    }
  }, [selectedMeeting, debriefingSession, joinDebriefingRoom, leaveDebriefingRoom]);

  const fetchMeetingAndSession = async (id) => {
    try {
      const [meetingRes, sessionRes] = await Promise.all([
        axios.get(`/api/v1/meetings/${id}/`),
        axios.get(`/api/v1/debriefings/?meeting=${id}`),
      ]);
      
      setSelectedMeeting(meetingRes.data);
      
      if (sessionRes.data.results?.length > 0) {
        setDebriefingSession(sessionRes.data.results[0]);
      } else {
        // Create new debriefing session
        const newSessionRes = await axios.post('/api/v1/debriefings/', {
          meeting: id,
        });
        setDebriefingSession(newSessionRes.data);
      }
    } catch (error) {
      console.error('Failed to fetch meeting and session:', error);
      toast.error('Failed to load debriefing session');
      navigate('/debriefing');
    } finally {
      setLoading(false);
    }
  };

  const fetchPendingMeetings = async () => {
    try {
      const response = await axios.get('/api/v1/meetings/?debriefing_needed=true');
      setMeetings(response.data.results || []);
      
      if (response.data.results?.length === 1) {
        // Auto-select if only one meeting
        const meeting = response.data.results[0];
        setSelectedMeeting(meeting);
        navigate(`/debriefing/${meeting.id}`);
      } else if (response.data.results?.length > 1) {
        setSelectMeetingOpen(true);
      }
    } catch (error) {
      console.error('Failed to fetch pending meetings:', error);
      toast.error('Failed to load meetings');
    } finally {
      setLoading(false);
    }
  };

  const handleMeetingSelect = (meeting) => {
    setSelectMeetingOpen(false);
    navigate(`/debriefing/${meeting.id}`);
  };

  const handleSessionUpdate = (updatedSession) => {
    setDebriefingSession(updatedSession);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <Typography>Loading debriefing session...</Typography>
      </Box>
    );
  }

  if (!selectedMeeting) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Meeting Debriefing
        </Typography>
        
        {meetings.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" gutterBottom>
              No meetings require debriefing
            </Typography>
            <Typography color="text.secondary" paragraph>
              All your recent meetings have been debriefed or are not yet ready for debriefing.
            </Typography>
            <Button
              variant="contained"
              onClick={() => navigate('/calendar')}
            >
              View Calendar
            </Button>
          </Paper>
        ) : (
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Select a meeting to debrief:
            </Typography>
            <List>
              {meetings.map((meeting) => (
                <ListItem
                  key={meeting.id}
                  button
                  onClick={() => handleMeetingSelect(meeting)}
                >
                  <ListItemText
                    primary={meeting.title}
                    secondary={`${new Date(meeting.start_time).toLocaleDateString()} - ${meeting.participants?.length || 0} participants`}
                  />
                  <Chip
                    label={meeting.meeting_type?.replace('_', ' ') || 'Unknown'}
                    size="small"
                    color="primary"
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        )}

        <Dialog
          open={selectMeetingOpen}
          onClose={() => setSelectMeetingOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Select Meeting to Debrief</DialogTitle>
          <DialogContent>
            <List>
              {meetings.map((meeting) => (
                <ListItem
                  key={meeting.id}
                  button
                  onClick={() => handleMeetingSelect(meeting)}
                >
                  <ListItemText
                    primary={meeting.title}
                    secondary={`${new Date(meeting.start_time).toLocaleDateString()} - ${meeting.participants?.length || 0} participants`}
                  />
                </ListItem>
              ))}
            </List>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setSelectMeetingOpen(false)}>Cancel</Button>
          </DialogActions>
        </Dialog>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Meeting Debriefing
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <MeetingSummary meeting={selectedMeeting} />
          {debriefingSession?.extracted_data && (
            <Box sx={{ mt: 2 }}>
              <ExtractedDataPreview data={debriefingSession.extracted_data} />
            </Box>
          )}
        </Grid>
        
        <Grid item xs={12} md={8}>
          {debriefingSession && (
            <DebriefingChat
              session={debriefingSession}
              meeting={selectedMeeting}
              onSessionUpdate={handleSessionUpdate}
            />
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default Debriefing;