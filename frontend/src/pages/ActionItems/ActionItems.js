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
  Tabs,
  Tab,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { DataGrid } from '@mui/x-data-grid';
import axios from 'axios';
import { toast } from 'react-toastify';
import { format, isAfter, isBefore, addDays } from 'date-fns';
import ActionItemDetails from './ActionItemDetails';
import ActionItemFilters from './ActionItemFilters';

const ActionItems = () => {
  const [actionItems, setActionItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  const [filters, setFilters] = useState({
    status: '',
    priority: '',
    owner: '',
    due_date_range: '',
  });
  const [pagination, setPagination] = useState({
    page: 0,
    pageSize: 25,
    total: 0,
  });

  useEffect(() => {
    fetchActionItems();
  }, [pagination.page, pagination.pageSize, searchTerm, filters, tabValue]);

  const fetchActionItems = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page + 1,
        page_size: pagination.pageSize,
        search: searchTerm,
        ...getTabFilters(),
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, value]) => value !== '')
        ),
      };

      const response = await axios.get('/api/v1/action-items/', { params });
      setActionItems(response.data.results || []);
      setPagination(prev => ({
        ...prev,
        total: response.data.count || 0,
      }));
    } catch (error) {
      console.error('Failed to fetch action items:', error);
      toast.error('Failed to load action items');
    } finally {
      setLoading(false);
    }
  };

  const getTabFilters = () => {
    switch (tabValue) {
      case 0: // All
        return {};
      case 1: // Pending
        return { status: 'pending' };
      case 2: // Overdue
        return { overdue: true };
      case 3: // Completed
        return { status: 'completed' };
      default:
        return {};
    }
  };

  const handleRowClick = (params) => {
    setSelectedItem(params.row);
    setDetailsOpen(true);
  };

  const handleFiltersApply = (newFilters) => {
    setFilters(newFilters);
    setPagination(prev => ({ ...prev, page: 0 }));
    setFiltersOpen(false);
  };

  const handleStatusUpdate = async (itemId, newStatus) => {
    try {
      await axios.patch(`/api/v1/action-items/${itemId}/`, {
        status: newStatus,
        completed_at: newStatus === 'completed' ? new Date().toISOString() : null,
      });
      
      toast.success(`Action item marked as ${newStatus}`);
      fetchActionItems();
    } catch (error) {
      console.error('Failed to update action item:', error);
      toast.error('Failed to update action item');
    }
  };

  const getPriorityColor = (priority) => {
    const colors = {
      high: 'error',
      medium: 'warning',
      low: 'info',
    };
    return colors[priority] || 'default';
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: 'warning',
      in_progress: 'info',
      completed: 'success',
      cancelled: 'error',
    };
    return colors[status] || 'default';
  };

  const isOverdue = (dueDate, status) => {
    if (!dueDate || status === 'completed') return false;
    return isBefore(new Date(dueDate), new Date());
  };

  const columns = [
    {
      field: 'description',
      headerName: 'Description',
      width: 300,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2">
            {params.value}
          </Typography>
          {isOverdue(params.row.due_date, params.row.status) && (
            <Chip
              label="Overdue"
              color="error"
              size="small"
              sx={{ mt: 0.5 }}
            />
          )}
        </Box>
      ),
    },
    {
      field: 'owner',
      headerName: 'Owner',
      width: 150,
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value}
          color={getPriorityColor(params.value)}
          size="small"
        />
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value.replace('_', ' ')}
          color={getStatusColor(params.value)}
          size="small"
        />
      ),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 120,
      valueFormatter: (params) => {
        if (!params.value) return 'No due date';
        return format(new Date(params.value), 'MMM dd, yyyy');
      },
    },
    {
      field: 'meeting',
      headerName: 'Meeting',
      width: 200,
      valueGetter: (params) => params.row.meeting?.title || 'N/A',
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      valueFormatter: (params) => format(new Date(params.value), 'MMM dd, yyyy'),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 150,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          {params.row.status === 'pending' && (
            <Button
              size="small"
              variant="outlined"
              onClick={(e) => {
                e.stopPropagation();
                handleStatusUpdate(params.row.id, 'completed');
              }}
            >
              Complete
            </Button>
          )}
          {params.row.status === 'completed' && (
            <Button
              size="small"
              variant="outlined"
              onClick={(e) => {
                e.stopPropagation();
                handleStatusUpdate(params.row.id, 'pending');
              }}
            >
              Reopen
            </Button>
          )}
        </Box>
      ),
    },
  ];

  const tabLabels = [
    'All',
    'Pending',
    'Overdue',
    'Completed',
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Action Items</Typography>
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
            onClick={() => {/* TODO: Add action item functionality */}}
          >
            Add Action Item
          </Button>
        </Box>
      </Box>

      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={tabValue}
          onChange={(e, newValue) => setTabValue(newValue)}
          indicatorColor="primary"
          textColor="primary"
        >
          {tabLabels.map((label, index) => (
            <Tab key={index} label={label} />
          ))}
        </Tabs>
      </Paper>

      <Paper sx={{ mb: 2, p: 2 }}>
        <TextField
          fullWidth
          placeholder="Search action items..."
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
          rows={actionItems}
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
        maxWidth="md"
        fullWidth
      >
        {selectedItem && (
          <ActionItemDetails
            actionItem={selectedItem}
            onClose={() => setDetailsOpen(false)}
            onUpdate={fetchActionItems}
            onStatusUpdate={handleStatusUpdate}
          />
        )}
      </Dialog>

      <Dialog
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <ActionItemFilters
          filters={filters}
          onApply={handleFiltersApply}
          onClose={() => setFiltersOpen(false)}
        />
      </Dialog>
    </Box>
  );
};

export default ActionItems;