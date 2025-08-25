import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Grid,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Divider,
  Alert,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
} from '@mui/material';
import {
  Person as ProfileIcon,
  Notifications as NotificationIcon,
  CalendarToday as CalendarIcon,
  Security as SecurityIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Check as CheckIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useAuth } from '../../contexts/AuthContext';

const Settings = () => {
  const [tabValue, setTabValue] = useState(0);
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
  });
  const [notifications, setNotifications] = useState({
    email_debriefing_reminders: true,
    email_meeting_updates: true,
    email_crm_sync_alerts: true,
    push_notifications: true,
    debriefing_reminder_frequency: 30,
  });
  const [calendarIntegrations, setCalendarIntegrations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const { user } = useAuth();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const [profileRes, notificationsRes, calendarRes] = await Promise.all([
        axios.get('/api/v1/auth/profile/'),
        axios.get('/api/v1/settings/settings/notifications/'),
        axios.get('/api/v1/calendar/providers/'),
      ]);
      
      setProfile(profileRes.data);
      setNotifications(notificationsRes.data);
      setCalendarIntegrations(calendarRes.data.providers || {});
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSave = async () => {
    try {
      await axios.patch('/api/v1/auth/profile/', profile);
      setSaveMessage('Profile updated successfully');
      toast.success('Profile updated successfully');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      console.error('Failed to update profile:', error);
      toast.error('Failed to update profile');
    }
  };

  const handleNotificationsSave = async () => {
    try {
      await axios.patch('/api/v1/settings/notifications/', notifications);
      setSaveMessage('Notification settings updated successfully');
      toast.success('Notification settings updated');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      console.error('Failed to update notifications:', error);
      toast.error('Failed to update notification settings');
    }
  };

  const handleCalendarConnect = async (provider) => {
    try {
      const response = await axios.post(`/api/v1/calendar/providers/${provider}/connect/`);
      if (response.data.auth_url) {
        // Open OAuth popup
        const popup = window.open(response.data.auth_url, '_blank', 'width=500,height=600');
        
        // Listen for OAuth callback messages
        const messageListener = (event) => {
          if (event.origin !== 'http://localhost:8000') return;
          
          if (event.data.type === 'calendar_oauth_success') {
            toast.success(event.data.message || 'Calendar connected successfully!');
            fetchSettings(); // Refresh settings to show connected calendar
            popup.close();
            window.removeEventListener('message', messageListener);
          } else if (event.data.type === 'calendar_oauth_error') {
            toast.error(`OAuth Error: ${event.data.error}`);
            popup.close();
            window.removeEventListener('message', messageListener);
          }
        };
        
        window.addEventListener('message', messageListener);
        
        // Clean up listener if popup is closed manually
        const checkClosed = setInterval(() => {
          if (popup.closed) {
            window.removeEventListener('message', messageListener);
            clearInterval(checkClosed);
          }
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to connect calendar:', error);
      toast.error('Failed to connect calendar');
    }
  };

  const handleCalendarSync = async (provider) => {
    try {
      toast.info('Syncing calendar events...');
      const response = await axios.post('/api/v1/calendar/sync/');
      toast.success(response.data.message || 'Calendar synced successfully!');
    } catch (error) {
      console.error('Failed to sync calendar:', error);
      toast.error(error.response?.data?.message || 'Failed to sync calendar');
    }
  };

  const handleCalendarDisconnect = async (integrationId) => {
    try {
      await axios.post(`/api/v1/calendar/providers/${integrationId}/disconnect/`);
      toast.success('Calendar disconnected');
      fetchSettings();
    } catch (error) {
      console.error('Failed to disconnect calendar:', error);
      toast.error('Failed to disconnect calendar');
    }
  };

  const renderProfile = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Profile Information
      </Typography>
      
      {saveMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {saveMessage}
        </Alert>
      )}
      
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name"
            value={profile.first_name}
            onChange={(e) => setProfile(prev => ({ ...prev, first_name: e.target.value }))}
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Last Name"
            value={profile.last_name}
            onChange={(e) => setProfile(prev => ({ ...prev, last_name: e.target.value }))}
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={profile.email}
            onChange={(e) => setProfile(prev => ({ ...prev, email: e.target.value }))}
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Phone"
            value={profile.phone}
            onChange={(e) => setProfile(prev => ({ ...prev, phone: e.target.value }))}
          />
        </Grid>
        
        <Grid item xs={12}>
          <Button
            variant="contained"
            onClick={handleProfileSave}
            disabled={loading}
          >
            Save Profile
          </Button>
        </Grid>
      </Grid>
    </Box>
  );

  const renderNotifications = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Notification Preferences
      </Typography>
      
      {saveMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {saveMessage}
        </Alert>
      )}
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Email Notifications
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={notifications.email_debriefing_reminders}
                onChange={(e) => setNotifications(prev => ({
                  ...prev,
                  email_debriefing_reminders: e.target.checked
                }))}
              />
            }
            label="Debriefing reminders"
          />
          
          <FormControlLabel
            control={
              <Switch
                checked={notifications.email_meeting_updates}
                onChange={(e) => setNotifications(prev => ({
                  ...prev,
                  email_meeting_updates: e.target.checked
                }))}
              />
            }
            label="Meeting updates"
          />
          
          <FormControlLabel
            control={
              <Switch
                checked={notifications.email_crm_sync_alerts}
                onChange={(e) => setNotifications(prev => ({
                  ...prev,
                  email_crm_sync_alerts: e.target.checked
                }))}
              />
            }
            label="CRM sync alerts"
          />
        </Grid>
        
        <Grid item xs={12}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" gutterBottom>
            Push Notifications
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={notifications.push_notifications}
                onChange={(e) => setNotifications(prev => ({
                  ...prev,
                  push_notifications: e.target.checked
                }))}
              />
            }
            label="Enable push notifications"
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Debriefing Reminder Frequency (minutes)"
            type="number"
            value={notifications.debriefing_reminder_frequency}
            onChange={(e) => setNotifications(prev => ({
              ...prev,
              debriefing_reminder_frequency: parseInt(e.target.value)
            }))}
            inputProps={{ min: 5, max: 120 }}
          />
        </Grid>
        
        <Grid item xs={12}>
          <Button
            variant="contained"
            onClick={handleNotificationsSave}
            disabled={loading}
          >
            Save Notification Settings
          </Button>
        </Grid>
      </Grid>
    </Box>
  );

  const renderCalendarIntegrations = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Calendar Integrations
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Connected Calendars
              </Typography>
              
              {Object.keys(calendarIntegrations).filter(key => calendarIntegrations[key].connected).length === 0 ? (
                <Typography color="text.secondary">
                  No calendars connected
                </Typography>
              ) : (
                <List>
                  {Object.entries(calendarIntegrations)
                    .filter(([key, provider]) => provider.connected)
                    .map(([key, provider]) => (
                    <ListItem key={key}>
                      <ListItemText
                        primary={provider.name}
                        secondary={`Status: Connected`}
                      />
                      <ListItemSecondaryAction>
                        <Button
                          size="small"
                          onClick={() => handleCalendarSync(key)}
                          sx={{ mr: 1 }}
                        >
                          Sync Now
                        </Button>
                        <IconButton
                          edge="end"
                          onClick={() => handleCalendarDisconnect(key)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Add Calendar
              </Typography>
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant={calendarIntegrations.google?.connected ? "contained" : "outlined"}
                  startIcon={calendarIntegrations.google?.connected ? <CheckIcon /> : <AddIcon />}
                  onClick={() => handleCalendarConnect('google')}
                  fullWidth
                  disabled={calendarIntegrations.google?.connected}
                  color={calendarIntegrations.google?.connected ? "success" : "primary"}
                >
                  {calendarIntegrations.google?.connected ? "Google Calendar Connected" : "Connect Google Calendar"}
                </Button>
                
                <Button
                  variant={calendarIntegrations.outlook?.connected ? "contained" : "outlined"}
                  startIcon={calendarIntegrations.outlook?.connected ? <CheckIcon /> : <AddIcon />}
                  onClick={() => handleCalendarConnect('outlook')}
                  fullWidth
                  disabled={calendarIntegrations.outlook?.connected}
                  color={calendarIntegrations.outlook?.connected ? "success" : "primary"}
                >
                  {calendarIntegrations.outlook?.connected ? "Outlook Calendar Connected" : "Connect Outlook Calendar"}
                </Button>
                
                <Button
                  variant={calendarIntegrations.exchange?.connected ? "contained" : "outlined"}
                  startIcon={calendarIntegrations.exchange?.connected ? <CheckIcon /> : <AddIcon />}
                  onClick={() => handleCalendarConnect('exchange')}
                  fullWidth
                  disabled={calendarIntegrations.exchange?.connected}
                  color={calendarIntegrations.exchange?.connected ? "success" : "primary"}
                >
                  {calendarIntegrations.exchange?.connected ? "Exchange Calendar Connected" : "Connect Exchange Calendar"}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  const renderSecurity = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Security Settings
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Change Password
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Current Password"
                    type="password"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="New Password"
                    type="password"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Confirm New Password"
                    type="password"
                  />
                </Grid>
                
                <Grid item xs={12}>
                  <Button variant="contained">
                    Update Password
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Two-Factor Authentication
              </Typography>
              
              <Typography variant="body2" color="text.secondary" paragraph>
                Add an extra layer of security to your account with two-factor authentication.
              </Typography>
              
              <Button variant="outlined">
                Enable 2FA
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  const tabs = [
    { label: 'Profile', icon: <ProfileIcon />, component: renderProfile },
    { label: 'Notifications', icon: <NotificationIcon />, component: renderNotifications },
    { label: 'Calendar', icon: <CalendarIcon />, component: renderCalendarIntegrations },
    { label: 'Security', icon: <SecurityIcon />, component: renderSecurity },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>
      
      <Paper sx={{ width: '100%' }}>
        <Tabs
          value={tabValue}
          onChange={(e, newValue) => setTabValue(newValue)}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
          scrollButtons="auto"
        >
          {tabs.map((tab, index) => (
            <Tab
              key={index}
              label={tab.label}
              icon={tab.icon}
              iconPosition="start"
            />
          ))}
        </Tabs>
        
        <Box sx={{ p: 3 }}>
          {tabs[tabValue].component()}
        </Box>
      </Paper>
    </Box>
  );
};

export default Settings;