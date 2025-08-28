import React, { createContext, useContext, useEffect, useState } from 'react';
import io from 'socket.io-client';
import { useAuth } from './AuthContext';
import { toast } from 'react-toastify';

const WebSocketContext = createContext();

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const { user } = useAuth();

  useEffect(() => {
    // Temporarily disable WebSocket connection
    // TODO: Implement WebSocket server support
    console.log('WebSocket connection disabled - will be implemented later');
    
    // if (user) {
    //   const newSocket = io('ws://localhost:8000', {
    //     auth: {
    //       token: localStorage.getItem('token'),
    //     },
    //   });

    //   newSocket.on('connect', () => {
    //     setConnected(true);
    //     console.log('WebSocket connected');
    //   });

    //   newSocket.on('disconnect', () => {
    //     setConnected(false);
    //     console.log('WebSocket disconnected');
    //   });

    //   newSocket.on('notification', (notification) => {
    //     setNotifications(prev => [notification, ...prev.slice(0, 49)]);
    //     toast.info(notification.message);
    //   });

    //   newSocket.on('meeting_update', (data) => {
    //     toast.info(`Meeting update: ${data.message}`);
    //   });

    //   newSocket.on('debriefing_reminder', (data) => {
    //     toast.warning(`Debriefing reminder: ${data.message}`);
    //   });

    //   newSocket.on('crm_sync_status', (data) => {
    //     if (data.status === 'error') {
    //       toast.error(`CRM Sync Error: ${data.message}`);
    //     } else {
    //       toast.success(`CRM Sync: ${data.message}`);
    //     }
    //   });

    //   setSocket(newSocket);

    //   return () => {
    //     newSocket.close();
    //   };
    // }
  }, [user]);

  const sendMessage = (event, data) => {
    if (socket && connected) {
      socket.emit(event, data);
    }
  };

  const joinDebriefingRoom = (meetingId) => {
    if (socket && connected) {
      socket.emit('join_debriefing', { meeting_id: meetingId });
    }
  };

  const leaveDebriefingRoom = (meetingId) => {
    if (socket && connected) {
      socket.emit('leave_debriefing', { meeting_id: meetingId });
    }
  };

  const markNotificationRead = (notificationId) => {
    setNotifications(prev => 
      prev.map(notif => 
        notif.id === notificationId 
          ? { ...notif, read: true }
          : notif
      )
    );
  };

  const clearNotifications = () => {
    setNotifications([]);
  };

  const value = {
    socket,
    connected,
    notifications,
    sendMessage,
    joinDebriefingRoom,
    leaveDebriefingRoom,
    markNotificationRead,
    clearNotifications,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};