import React from 'react';
import {
  Menu,
  MenuItem,
  Typography,
  Box,
  Divider,
  IconButton,
  Badge,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as CheckIcon,
  Clear as ClearAllIcon,
} from '@mui/icons-material';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { formatDistanceToNow } from 'date-fns';

const NotificationPanel = ({ anchorEl, open, onClose }) => {
  const { notifications, markNotificationRead, clearNotifications } = useWebSocket();

  const handleMarkRead = (notificationId) => {
    markNotificationRead(notificationId);
  };

  const handleClearAll = () => {
    clearNotifications();
  };

  return (
    <Menu
      anchorEl={anchorEl}
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: 350,
          maxHeight: 400,
        },
      }}
      transformOrigin={{ horizontal: 'right', vertical: 'top' }}
      anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
    >
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">Notifications</Typography>
        <Box>
          <IconButton size="small" onClick={handleClearAll} title="Clear all">
            <ClearAllIcon />
          </IconButton>
          <IconButton size="small" onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>
      <Divider />
      
      {notifications.length === 0 ? (
        <MenuItem>
          <Typography variant="body2" color="text.secondary">
            No notifications
          </Typography>
        </MenuItem>
      ) : (
        <List sx={{ p: 0, maxHeight: 300, overflow: 'auto' }}>
          {notifications.map((notification) => (
            <ListItem
              key={notification.id}
              sx={{
                backgroundColor: notification.read ? 'transparent' : 'action.hover',
                borderLeft: notification.read ? 'none' : '3px solid primary.main',
              }}
            >
              <ListItemText
                primary={notification.title || 'Notification'}
                secondary={
                  <Box>
                    <Typography variant="body2" component="div">
                      {notification.message}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDistanceToNow(new Date(notification.timestamp), { addSuffix: true })}
                    </Typography>
                  </Box>
                }
              />
              {!notification.read && (
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => handleMarkRead(notification.id)}
                    title="Mark as read"
                  >
                    <CheckIcon fontSize="small" />
                  </IconButton>
                </ListItemSecondaryAction>
              )}
            </ListItem>
          ))}
        </List>
      )}
    </Menu>
  );
};

export default NotificationPanel;