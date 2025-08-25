import React, { useState } from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Grid,
} from '@mui/material';

const ActionItemFilters = ({ filters, onApply, onClose }) => {
  const [localFilters, setLocalFilters] = useState(filters);

  const handleChange = (field) => (event) => {
    setLocalFilters(prev => ({
      ...prev,
      [field]: event.target.value,
    }));
  };

  const handleApply = () => {
    onApply(localFilters);
  };

  const handleReset = () => {
    const resetFilters = {
      status: '',
      priority: '',
      owner: '',
      due_date_range: '',
    };
    setLocalFilters(resetFilters);
    onApply(resetFilters);
  };

  return (
    <>
      <DialogTitle>Filter Action Items</DialogTitle>
      
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={localFilters.status}
                onChange={handleChange('status')}
                label="Status"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="cancelled">Cancelled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={localFilters.priority}
                onChange={handleChange('priority')}
                label="Priority"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="low">Low</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Owner"
              value={localFilters.owner}
              onChange={handleChange('owner')}
              placeholder="Filter by owner name..."
            />
          </Grid>
          
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>Due Date</InputLabel>
              <Select
                value={localFilters.due_date_range}
                onChange={handleChange('due_date_range')}
                label="Due Date"
              >
                <MenuItem value="">Any time</MenuItem>
                <MenuItem value="overdue">Overdue</MenuItem>
                <MenuItem value="today">Due today</MenuItem>
                <MenuItem value="this_week">Due this week</MenuItem>
                <MenuItem value="this_month">Due this month</MenuItem>
                <MenuItem value="no_due_date">No due date</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleReset}>Reset</Button>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleApply}>
          Apply Filters
        </Button>
      </DialogActions>
    </>
  );
};

export default ActionItemFilters;