import React from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
  Grid,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
  TrendingUp as StrengthIcon,
  TrendingDown as WeaknessIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

const CompetitorDetails = ({ competitor, onClose }) => {
  const getThreatLevelColor = (level) => {
    const colors = {
      high: 'error',
      medium: 'warning',
      low: 'success',
    };
    return colors[level] || 'default';
  };

  const getThreatLevelIcon = (level) => {
    const icons = {
      high: <WarningIcon />,
      medium: <InfoIcon />,
      low: <SuccessIcon />,
    };
    return icons[level] || <InfoIcon />;
  };

  return (
    <>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">{competitor.competitor_name}</Typography>
          <Chip
            icon={getThreatLevelIcon(competitor.threat_level)}
            label={`${competitor.threat_level} threat`}
            color={getThreatLevelColor(competitor.threat_level)}
          />
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Context
            </Typography>
            <Typography variant="body1" paragraph>
              {competitor.competitive_context}
            </Typography>
          </Grid>

          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom>
              <StrengthIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Strengths Mentioned
            </Typography>
            {competitor.strengths_mentioned?.length > 0 ? (
              <List dense>
                {competitor.strengths_mentioned.map((strength, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={strength}
                      primaryTypographyProps={{ variant: 'body2' }}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography color="text.secondary">No strengths mentioned</Typography>
            )}
          </Grid>

          <Grid item xs={12} md={6}>
            <Typography variant="h6" gutterBottom>
              <WeaknessIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Weaknesses Mentioned
            </Typography>
            {competitor.weaknesses_mentioned?.length > 0 ? (
              <List dense>
                {competitor.weaknesses_mentioned.map((weakness, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={weakness}
                      primaryTypographyProps={{ variant: 'body2' }}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography color="text.secondary">No weaknesses mentioned</Typography>
            )}
          </Grid>

          {competitor.pricing_intelligence && Object.keys(competitor.pricing_intelligence).length > 0 && (
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Pricing Intelligence
              </Typography>
              <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                {Object.entries(competitor.pricing_intelligence).map(([key, value]) => (
                  <Typography key={key} variant="body2" sx={{ mb: 1 }}>
                    <strong>{key.replace('_', ' ')}:</strong> {value}
                  </Typography>
                ))}
              </Box>
            </Grid>
          )}

          {competitor.relationship_status && (
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Relationship Status
              </Typography>
              <Chip
                label={competitor.relationship_status}
                color="info"
                variant="outlined"
              />
            </Grid>
          )}

          <Grid item xs={12}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="h6" gutterBottom>
              Meeting Information
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Meeting:</strong> {competitor.meeting?.title || 'Unknown'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Lead:</strong> {competitor.lead?.first_name} {competitor.lead?.last_name} ({competitor.lead?.company})
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Captured:</strong> {format(new Date(competitor.created_at), 'MMM dd, yyyy HH:mm')}
            </Typography>
          </Grid>
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button variant="contained" onClick={() => {/* TODO: Edit competitor intel */}}>
          Edit
        </Button>
      </DialogActions>
    </>
  );
};

export default CompetitorDetails;