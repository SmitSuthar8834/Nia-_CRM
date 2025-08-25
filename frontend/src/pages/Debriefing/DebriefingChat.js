import React, { useState, useEffect, useRef } from 'react';
import {
  Paper,
  Box,
  Typography,
  TextField,
  Button,
  List,
  ListItem,
  Avatar,
  Chip,
  CircularProgress,
  IconButton,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as AIIcon,
  Person as PersonIcon,
  CheckCircle as CompleteIcon,
} from '@mui/icons-material';
import { useWebSocket } from '../../contexts/WebSocketContext';
import axios from 'axios';
import { toast } from 'react-toastify';

const DebriefingChat = ({ session, meeting, onSessionUpdate }) => {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionStatus, setSessionStatus] = useState(session.status);
  const messagesEndRef = useRef(null);
  const { socket } = useWebSocket();

  useEffect(() => {
    // Load existing conversation
    if (session.conversation_data?.messages) {
      setMessages(session.conversation_data.messages);
    } else {
      // Start new conversation
      startDebriefing();
    }
  }, [session]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (socket) {
      socket.on('debriefing_message', handleIncomingMessage);
      socket.on('debriefing_complete', handleDebriefingComplete);
      
      return () => {
        socket.off('debriefing_message', handleIncomingMessage);
        socket.off('debriefing_complete', handleDebriefingComplete);
      };
    }
  }, [socket]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const startDebriefing = async () => {
    try {
      setIsTyping(true);
      const response = await axios.post(`/api/v1/debriefings/${session.id}/start/`);
      
      if (response.data.initial_message) {
        const aiMessage = {
          id: Date.now(),
          type: 'ai',
          content: response.data.initial_message,
          timestamp: new Date().toISOString(),
        };
        setMessages([aiMessage]);
      }
    } catch (error) {
      console.error('Failed to start debriefing:', error);
      toast.error('Failed to start debriefing session');
    } finally {
      setIsTyping(false);
    }
  };

  const handleIncomingMessage = (data) => {
    if (data.session_id === session.id) {
      const aiMessage = {
        id: Date.now(),
        type: 'ai',
        content: data.message,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, aiMessage]);
      setIsTyping(false);
    }
  };

  const handleDebriefingComplete = (data) => {
    if (data.session_id === session.id) {
      setSessionStatus('completed');
      onSessionUpdate({ ...session, status: 'completed', extracted_data: data.extracted_data });
      toast.success('Debriefing completed successfully!');
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim()) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: currentMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsTyping(true);

    try {
      await axios.post(`/api/v1/debriefings/${session.id}/respond/`, {
        message: currentMessage,
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error('Failed to send message');
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const completeDebriefing = async () => {
    try {
      await axios.post(`/api/v1/debriefings/${session.id}/complete/`);
      setSessionStatus('completed');
      toast.success('Debriefing marked as complete');
    } catch (error) {
      console.error('Failed to complete debriefing:', error);
      toast.error('Failed to complete debriefing');
    }
  };

  return (
    <Paper sx={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">AI Debriefing Session</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={sessionStatus}
              color={sessionStatus === 'completed' ? 'success' : 'primary'}
              size="small"
            />
            {sessionStatus !== 'completed' && messages.length > 2 && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<CompleteIcon />}
                onClick={completeDebriefing}
              >
                Complete
              </Button>
            )}
          </Box>
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 1 }}>
        <List>
          {messages.map((message) => (
            <ListItem
              key={message.id}
              sx={{
                display: 'flex',
                justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start',
                alignItems: 'flex-start',
                mb: 1,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: message.type === 'user' ? 'row-reverse' : 'row',
                  alignItems: 'flex-start',
                  maxWidth: '80%',
                  gap: 1,
                }}
              >
                <Avatar
                  sx={{
                    bgcolor: message.type === 'user' ? 'primary.main' : 'secondary.main',
                    width: 32,
                    height: 32,
                  }}
                >
                  {message.type === 'user' ? <PersonIcon /> : <AIIcon />}
                </Avatar>
                
                <Paper
                  sx={{
                    p: 2,
                    bgcolor: message.type === 'user' ? 'primary.light' : 'grey.100',
                    color: message.type === 'user' ? 'primary.contrastText' : 'text.primary',
                  }}
                >
                  <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                    {message.content}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      mt: 0.5,
                      opacity: 0.7,
                    }}
                  >
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </Typography>
                </Paper>
              </Box>
            </ListItem>
          ))}
          
          {isTyping && (
            <ListItem sx={{ justifyContent: 'flex-start' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Avatar sx={{ bgcolor: 'secondary.main', width: 32, height: 32 }}>
                  <AIIcon />
                </Avatar>
                <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={16} />
                    <Typography variant="body2" color="text.secondary">
                      AI is thinking...
                    </Typography>
                  </Box>
                </Paper>
              </Box>
            </ListItem>
          )}
        </List>
        <div ref={messagesEndRef} />
      </Box>

      {sessionStatus !== 'completed' && (
        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              multiline
              maxRows={3}
              placeholder="Type your response..."
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isTyping}
            />
            <IconButton
              color="primary"
              onClick={sendMessage}
              disabled={!currentMessage.trim() || isTyping}
            >
              <SendIcon />
            </IconButton>
          </Box>
        </Box>
      )}
    </Paper>
  );
};

export default DebriefingChat;