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

const ActionItemsSummary = ({ actionItems }) => {
  const navigate = useNavigate();

  const getPriorityColor = (priority) => {
    const colors = {
      high: 'error',
      medium: 'warning',
      low: 'info',
    };
    return colors[priority] || 'default';
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Pending Action Items</Typography>
        <Button size="small" onClick={() => navigate('/action-items')}>
          View All
        </Button>
      </Box>
      
      {actionItems.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4 }}>
          <Typography color="text.secondary">No pending action items</Typography>
        </Box>
      ) : (
        <List>
          {actionItems.map((item) => (
            <ListItem key={item.id} divider>
              <ListItemText
                primary={item.description}
                secondary={
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Owner: {item.owner}
                    </Typography>
                    {item.due_date && (
                      <Typography variant="caption" color="text.secondary">
                        Due: {format(new Date(item.due_date), 'MMM dd, yyyy')}
                      </Typography>
                    )}
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Chip
                  label={item.priority}
                  size="small"
                  color={getPriorityColor(item.priority)}
                />
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
};

export default ActionItemsSummary;