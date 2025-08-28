import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  InputAdornment,
  Chip,
  Dialog,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import axios from 'axios';
import { toast } from 'react-toastify';
import LeadDetails from './LeadDetails';
import LeadFilters from './LeadFilters';

const LeadManagement = () => {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLead, setSelectedLead] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState({
    status: '',
    source: '',
    qualification_score_min: '',
    qualification_score_max: '',
    last_meeting_days: '',
  });
  const [pagination, setPagination] = useState({
    page: 0,
    pageSize: 25,
    total: 0,
  });

  useEffect(() => {
    fetchLeads();
  }, [pagination.page, pagination.pageSize, searchTerm, filters]);

  const fetchLeads = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page + 1,
        page_size: pagination.pageSize,
        search: searchTerm,
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, value]) => value !== '')
        ),
      };

      const response = await axios.get('/api/v1/leads/', { params });
      setLeads(response.data.results || []);
      setPagination(prev => ({
        ...prev,
        total: response.data.count || 0,
      }));
    } catch (error) {
      console.error('Failed to fetch leads:', error);
      toast.error('Failed to load leads');
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (params) => {
    setSelectedLead(params.row);
    setDetailsOpen(true);
  };

  const handleFiltersApply = (newFilters) => {
    setFilters(newFilters);
    setPagination(prev => ({ ...prev, page: 0 }));
    setFiltersOpen(false);
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'info',
      qualified: 'success',
      unqualified: 'error',
      contacted: 'warning',
      converted: 'primary',
    };
    return colors[status] || 'default';
  };

  const getQualificationScoreColor = (score) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  const columns = [
    {
      field: 'full_name',
      headerName: 'Name',
      width: 200,
      valueGetter: (params) => `${params.row.first_name} ${params.row.last_name}`,
    },
    {
      field: 'email',
      headerName: 'Email',
      width: 250,
    },
    {
      field: 'company',
      headerName: 'Company',
      width: 200,
    },
    {
      field: 'title',
      headerName: 'Title',
      width: 150,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={getStatusColor(params.value)}
          size="small"
        />
      ),
    },
    {
      field: 'qualification_score',
      headerName: 'Score',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={`${params.value}%`}
          color={getQualificationScoreColor(params.value)}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      field: 'meeting_count',
      headerName: 'Meetings',
      width: 100,
      align: 'center',
    },
    {
      field: 'last_meeting_date',
      headerName: 'Last Meeting',
      width: 150,
      valueFormatter: (params) => {
        if (!params.value) return 'Never';
        return new Date(params.value).toLocaleDateString();
      },
    },
    {
      field: 'source',
      headerName: 'Source',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          variant="outlined"
        />
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Lead Management</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            startIcon={<FilterIcon />}
            onClick={() => setFiltersOpen(true)}
          >
            Filters
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {/* TODO: Add lead functionality */}}
          >
            Add Lead
          </Button>
        </Box>
      </Box>

      <Paper sx={{ mb: 2, p: 2 }}>
        <TextField
          fullWidth
          placeholder="Search leads by name, email, or company..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      <Paper sx={{ height: 600 }}>
        <DataGrid
          rows={leads}
          columns={columns}
          loading={loading}
          pagination
          paginationMode="server"
          rowCount={pagination.total}
          page={pagination.page}
          pageSize={pagination.pageSize}
          onPageChange={(newPage) => setPagination(prev => ({ ...prev, page: newPage }))}
          onPageSizeChange={(newPageSize) => setPagination(prev => ({ ...prev, pageSize: newPageSize }))}
          pageSizeOptions={[10, 25, 50, 100]}
          onRowClick={handleRowClick}
          sx={{
            '& .MuiDataGrid-row': {
              cursor: 'pointer',
            },
          }}
        />
      </Paper>

      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        {selectedLead && (
          <LeadDetails
            lead={selectedLead}
            onClose={() => setDetailsOpen(false)}
            onUpdate={fetchLeads}
          />
        )}
      </Dialog>

      <Dialog
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <LeadFilters
          filters={filters}
          onApply={handleFiltersApply}
          onClose={() => setFiltersOpen(false)}
        />
      </Dialog>
    </Box>
  );
};

export default LeadManagement;