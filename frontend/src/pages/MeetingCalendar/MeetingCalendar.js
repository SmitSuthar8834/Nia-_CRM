import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  RecordVoiceOver as DebriefingIcon,
  People as ParticipantsIcon,
} from '@mui/icons-material';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import { format, isSameDay } from 'date-fns';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useNavigate } from 'react-router-dom';
import MeetingCard from './MeetingCard';
import MeetingDetails from './MeetingDetails';

const MeetingCalendar = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchMeetings();
  }, [selectedDate]);

  const fetchMeetings = async () => {
    try {
      const startDate = format(selectedDate, 'yyyy-MM-dd');
      const response = await axios.get(`/api/v1/meetings/?date=${startDate}`);
      setMeetings(response.data.results || []);
    } catch (error) {
      console.error('Failed to fetch meetings:', error);
      toast.error('Failed to load meetings');
    } finally {
      setLoading(false);
    }
  };

  const handleDateChange = (date) => {
    setSelectedDate(date);
  };

  const handleMeetingClick = (meeting) => {
    setSelectedMeeting(meeting);
    setDetailsOpen(true);
  };

  const handleStartDebriefing = (meetingId) => {
    navigate(`/debriefing/${meetingId}`);
  };

  const handleRefresh = () => {
    setLoading(true);
    fetchMeetings();
  };

  const getMeetingsForDate = (date) => {
    return meetings.filter(meeting => 
      isSameDay(new Date(meeting.start_time), date)
    );
  };

  const tileContent = ({ date, view }) => {
    if (view === 'month') {
      const dayMeetings = getMeetingsForDate(date);
      if (dayMeetings.length > 0) {
        return (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 0.5 }}>
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: 'primary.main',
              }}
            />
          </Box>
        );
      }
    }
    return null;
  };

  const selectedDateMeetings = getMeetingsForDate(selectedDate);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Meeting Calendar</Typography>
        <Box>
          <Button
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            sx={{ mr: 1 }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {/* TODO: Add meeting functionality */}}
          >
            Add Meeting
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Calendar
            </Typography>
            <Calendar
              onChange={handleDateChange}
              value={selectedDate}
              tileContent={tileContent}
              className="meeting-calendar"
            />
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Meetings for {format(selectedDate, 'MMMM dd, yyyy')}
            </Typography>
            
            {loading ? (
              <Typography>Loading meetings...</Typography>
            ) : selectedDateMeetings.length === 0 ? (
              <Typography color="text.secondary">
                No meetings scheduled for this date
              </Typography>
            ) : (
              <List>
                {selectedDateMeetings.map((meeting) => (
                  <MeetingCard
                    key={meeting.id}
                    meeting={meeting}
                    onClick={() => handleMeetingClick(meeting)}
                    onStartDebriefing={() => handleStartDebriefing(meeting.id)}
                  />
                ))}
              </List>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        {selectedMeeting && (
          <MeetingDetails
            meeting={selectedMeeting}
            onClose={() => setDetailsOpen(false)}
            onStartDebriefing={() => {
              setDetailsOpen(false);
              handleStartDebriefing(selectedMeeting.id);
            }}
          />
        )}
      </Dialog>
    </Box>
  );
};

export default MeetingCalendar;