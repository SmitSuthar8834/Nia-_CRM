import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Chip,
  Button,
  Dialog,
} from '@mui/material';
import {
  TrendingUp as TrendingIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import axios from 'axios';
import { toast } from 'react-toastify';
import CompetitorDetails from './CompetitorDetails';

const CompetitiveIntelligence = () => {
  const [competitiveData, setCompetitiveData] = useState([]);
  const [summary, setSummary] = useState({});
  const [selectedCompetitor, setSelectedCompetitor] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCompetitiveIntelligence();
  }, []);

  const fetchCompetitiveIntelligence = async () => {
    try {
      const [dataRes, summaryRes] = await Promise.all([
        axios.get('/api/v1/competitive-intelligence/'),
        axios.get('/api/v1/competitive-intelligence/summary/'),
      ]);
      
      setCompetitiveData(dataRes.data.results || []);
      setSummary(summaryRes.data || {});
    } catch (error) {
      console.error('Failed to fetch competitive intelligence:', error);
      toast.error('Failed to load competitive intelligence');
    } finally {
      setLoading(false);
    }
  };

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

  const threatLevelData = summary.threat_levels ? Object.entries(summary.threat_levels).map(([level, count]) => ({
    name: level,
    value: count,
    color: level === 'high' ? '#f44336' : level === 'medium' ? '#ff9800' : '#4caf50',
  })) : [];

  const competitorMentions = summary.top_competitors ? summary.top_competitors.map(comp => ({
    name: comp.name,
    mentions: comp.mention_count,
  })) : [];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <Typography>Loading competitive intelligence...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Competitive Intelligence
      </Typography>

      <Grid container spacing={3}>
        {/* Summary Cards */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Competitors
                  </Typography>
                  <Typography variant="h4">
                    {summary.total_competitors || 0}
                  </Typography>
                </Box>
                <TrendingIcon color="primary" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    High Threat
                  </Typography>
                  <Typography variant="h4" color="error">
                    {summary.threat_levels?.high || 0}
                  </Typography>
                </Box>
                <WarningIcon color="error" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Recent Mentions
                  </Typography>
                  <Typography variant="h4">
                    {summary.recent_mentions || 0}
                  </Typography>
                </Box>
                <InfoIcon color="info" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Opportunities
                  </Typography>
                  <Typography variant="h4" color="success">
                    {summary.opportunities || 0}
                  </Typography>
                </Box>
                <SuccessIcon color="success" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Charts */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: 300 }}>
            <Typography variant="h6" gutterBottom>
              Threat Level Distribution
            </Typography>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={threatLevelData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {threatLevelData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, height: 300 }}>
            <Typography variant="h6" gutterBottom>
              Top Competitors by Mentions
            </Typography>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={competitorMentions}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="mentions" fill="#1976d2" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Recent Intelligence */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Recent Competitive Intelligence</Typography>
              <Button variant="outlined" onClick={fetchCompetitiveIntelligence}>
                Refresh
              </Button>
            </Box>
            
            {competitiveData.length === 0 ? (
              <Typography color="text.secondary">
                No competitive intelligence data available
              </Typography>
            ) : (
              <List>
                {competitiveData.slice(0, 10).map((intel) => (
                  <ListItem
                    key={intel.id}
                    divider
                    sx={{ cursor: 'pointer' }}
                    onClick={() => {
                      setSelectedCompetitor(intel);
                      setDetailsOpen(true);
                    }}
                  >
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="subtitle1">
                            {intel.competitor_name}
                          </Typography>
                          <Chip
                            icon={getThreatLevelIcon(intel.threat_level)}
                            label={intel.threat_level}
                            color={getThreatLevelColor(intel.threat_level)}
                            size="small"
                          />
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            {intel.competitive_context}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            From meeting: {intel.meeting?.title} - {new Date(intel.created_at).toLocaleDateString()}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
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
        {selectedCompetitor && (
          <CompetitorDetails
            competitor={selectedCompetitor}
            onClose={() => setDetailsOpen(false)}
          />
        )}
      </Dialog>
    </Box>
  );
};

export default CompetitiveIntelligence;