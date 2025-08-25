import React, { useState } from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Box,
} from '@mui/material';

const LeadFilters = ({ filters, onApply, onClose }) => {
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
      source: '',
      qualification_score_min: '',
      qualification_score_max: '',
      last_meeting_days: '',
    };
    setLocalFilters(resetFilters);
    onApply(resetFilters);
  };

  return (
    <>
      <DialogTitle>Filter Leads</DialogTitle>
      
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
                <MenuItem value="new">New</MenuItem>
                <MenuItem value="contacted">Contacted</MenuItem>
                <MenuItem value="qualified">Qualified</MenuItem>
                <MenuItem value="unqualified">Unqualified</MenuItem>
                <MenuItem value="converted">Converted</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={localFilters.source}
                onChange={handleChange('source')}
                label="Source"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="meeting">Meeting</MenuItem>
                <MenuItem value="calendar">Calendar</MenuItem>
                <MenuItem value="manual">Manual</MenuItem>
                <MenuItem value="import">Import</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Min Qualification Score"
              type="number"
              value={localFilters.qualification_score_min}
              onChange={handleChange('qualification_score_min')}
              inputProps={{ min: 0, max: 100 }}
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Max Qualification Score"
              type="number"
              value={localFilters.qualification_score_max}
              onChange={handleChange('qualification_score_max')}
              inputProps={{ min: 0, max: 100 }}
            />
          </Grid>
          
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>Last Meeting</InputLabel>
              <Select
                value={localFilters.last_meeting_days}
                onChange={handleChange('last_meeting_days')}
                label="Last Meeting"
              >
                <MenuItem value="">Any time</MenuItem>
                <MenuItem value="7">Last 7 days</MenuItem>
                <MenuItem value="30">Last 30 days</MenuItem>
                <MenuItem value="90">Last 90 days</MenuItem>
                <MenuItem value="365">Last year</MenuItem>
                <MenuItem value="never">Never</MenuItem>
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

export default LeadFilters;