import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
  Assignment as AssignmentIcon,
  TrendingUp as CompetitiveIcon,
} from '@mui/icons-material';

const ExtractedDataPreview = ({ data }) => {
  const [expanded, setExpanded] = useState('contacts');

  const handleChange = (panel) => (event, isExpanded) => {
    setExpanded(isExpanded ? panel : false);
  };

  const renderContacts = () => {
    if (!data.contacts || data.contacts.length === 0) {
      return <Typography color="text.secondary">No contacts extracted</Typography>;
    }

    return (
      <List dense>
        {data.contacts.map((contact, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={`${contact.first_name} ${contact.last_name}`}
              secondary={
                <Box>
                  {contact.title && <Typography variant="caption" display="block">{contact.title}</Typography>}
                  {contact.company && <Typography variant="caption" display="block">{contact.company}</Typography>}
                  {contact.email && <Typography variant="caption" display="block">{contact.email}</Typography>}
                </Box>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderDeals = () => {
    if (!data.deals || data.deals.length === 0) {
      return <Typography color="text.secondary">No deal information extracted</Typography>;
    }

    return (
      <List dense>
        {data.deals.map((deal, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={deal.opportunity_name || 'Unnamed Opportunity'}
              secondary={
                <Box>
                  {deal.budget && <Typography variant="caption" display="block">Budget: {deal.budget}</Typography>}
                  {deal.timeline && <Typography variant="caption" display="block">Timeline: {deal.timeline}</Typography>}
                  {deal.decision_makers && (
                    <Typography variant="caption" display="block">
                      Decision Makers: {deal.decision_makers.join(', ')}
                    </Typography>
                  )}
                </Box>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderActionItems = () => {
    if (!data.action_items || data.action_items.length === 0) {
      return <Typography color="text.secondary">No action items extracted</Typography>;
    }

    return (
      <List dense>
        {data.action_items.map((item, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={item.description}
              secondary={
                <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                  <Chip label={item.owner} size="small" />
                  <Chip label={item.priority} size="small" color="warning" />
                  {item.due_date && (
                    <Chip label={`Due: ${item.due_date}`} size="small" color="info" />
                  )}
                </Box>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderCompetitiveIntel = () => {
    if (!data.competitive_intelligence || data.competitive_intelligence.length === 0) {
      return <Typography color="text.secondary">No competitive intelligence extracted</Typography>;
    }

    return (
      <List dense>
        {data.competitive_intelligence.map((intel, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={intel.competitor_name}
              secondary={
                <Box>
                  <Typography variant="caption" display="block">
                    Context: {intel.competitive_context}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                    <Chip label={intel.threat_level} size="small" color="error" />
                  </Box>
                </Box>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  return (
    <Paper sx={{ mt: 2 }}>
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6">Extracted Data</Typography>
      </Box>

      <Accordion expanded={expanded === 'contacts'} onChange={handleChange('contacts')}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PersonIcon fontSize="small" />
            <Typography>Contacts ({data.contacts?.length || 0})</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {renderContacts()}
        </AccordionDetails>
      </Accordion>

      <Accordion expanded={expanded === 'deals'} onChange={handleChange('deals')}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BusinessIcon fontSize="small" />
            <Typography>Deal Information ({data.deals?.length || 0})</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {renderDeals()}
        </AccordionDetails>
      </Accordion>

      <Accordion expanded={expanded === 'actions'} onChange={handleChange('actions')}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AssignmentIcon fontSize="small" />
            <Typography>Action Items ({data.action_items?.length || 0})</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {renderActionItems()}
        </AccordionDetails>
      </Accordion>

      <Accordion expanded={expanded === 'competitive'} onChange={handleChange('competitive')}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CompetitiveIcon fontSize="small" />
            <Typography>Competitive Intel ({data.competitive_intelligence?.length || 0})</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {renderCompetitiveIntel()}
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
};

export default ExtractedDataPreview;