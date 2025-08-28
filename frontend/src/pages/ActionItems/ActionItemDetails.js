import React from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Grid,
  Divider,
} from '@mui/material';
import {
  Assignment as AssignmentIcon,
  Person as PersonIcon,
  CalendarToday as CalendarIcon,
  Flag as PriorityIcon,
} from '@mui/icons-material';
import { format, isBefore } from 'date-fns';

const ActionItemDetails = ({ actionItem, onClose, onUpdate, onStatusUpdate }) => {
  const getPriorityColor = (priority) => {
    const colors = {
      high: 'error',
      medium: 'warning',
      low: 'info',
    };
    return colors[priority] || 'default';
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: 'warning',
      in_progress: 'info',
      completed: 'success',
      cancelled: 'error',
    };
    return colors[status] || 'default';
  };

  const isOverdue = (dueDate, status) => {
    if (!dueDate || status === 'completed') return false;
    return isBefore(new Date(dueDate), new Date());
  };

  const handleStatusChange = (newStatus) => {
    onStatusUpdate(actionItem.id, newStatus);
    onClose();
  };

  return (
    <>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Action Item Details</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={actionItem.status.replace('_', ' ')}
              color={getStatusColor(actionItem.status)}
            />
            {isOverdue(actionItem.due_date, actionItem.status) && (
              <Chip label="Overdue" color="error" />
            )}
          </Box>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              <AssignmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Description
            </Typography>
            <Typography variant="body1" paragraph>
              {actionItem.description}
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom>
              Details
            </Typography>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <PersonIcon fontSize="small" color="action" />
              <Typography variant="body2">
                <strong>Owner:</strong> {actionItem.owner}
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <PriorityIcon fontSize="small" color="action" />
              <Typography variant="body2">
                <strong>Priority:</strong>
              </Typography>
              <Chip
                label={actionItem.priority}
                color={getPriorityColor(actionItem.priority)}
                size="small"
              />
            </Box>
            
            {actionItem.due_date && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <CalendarIcon fontSize="small" color="action" />
                <Typography variant="body2">
                  <strong>Due Date:</strong> {format(new Date(actionItem.due_date), 'MMM dd, yyyy')}
                </Typography>
              </Box>
            )}
            
            {actionItem.is_commitment && (
              <Box sx={{ mb: 1 }}>
                <Chip
                  label="Commitment"
                  color="secondary"
                  size="small"
                  variant="outlined"
                />
              </Box>
            )}
          </Grid>

          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom>
              Timeline
            </Typography>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              <strong>Created:</strong> {format(new Date(actionItem.created_at), 'MMM dd, yyyy HH:mm')}
            </Typography>
            
            {actionItem.completed_at && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                <strong>Completed:</strong> {format(new Date(actionItem.completed_at), 'MMM dd, yyyy HH:mm')}
              </Typography>
            )}
          </Grid>

          {actionItem.meeting && (
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="h6" gutterBottom>
                Related Meeting
              </Typography>
              <Typography variant="body2">
                <strong>Meeting:</strong> {actionItem.meeting.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {format(new Date(actionItem.meeting.start_time), 'MMM dd, yyyy HH:mm')}
              </Typography>
            </Grid>
          )}

          {actionItem.debriefing_session && (
            <Grid item xs={12}>
              <Typography variant="body2" color="text.secondary">
                <strong>From Debriefing Session:</strong> {actionItem.debriefing_session.id}
              </Typography>
            </Grid>
          )}
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        
        {actionItem.status === 'pending' && (
          <>
            <Button
              variant="outlined"
              onClick={() => handleStatusChange('in_progress')}
            >
              Start Progress
            </Button>
            <Button
              variant="contained"
              color="success"
              onClick={() => handleStatusChange('completed')}
            >
              Mark Complete
            </Button>
          </>
        )}
        
        {actionItem.status === 'in_progress' && (
          <Button
            variant="contained"
            color="success"
            onClick={() => handleStatusChange('completed')}
          >
            Mark Complete
          </Button>
        )}
        
        {actionItem.status === 'completed' && (
          <Button
            variant="outlined"
            onClick={() => handleStatusChange('pending')}
          >
            Reopen
          </Button>
        )}
      </DialogActions>
    </>
  );
};

export default ActionItemDetails;