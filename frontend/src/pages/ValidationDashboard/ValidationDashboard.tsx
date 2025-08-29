import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    Grid,
    Chip,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    TextField,
    MenuItem,
    IconButton,
    Tooltip,
    Alert,
} from '@mui/material';
import {
    Visibility as VisibilityIcon,
    Refresh as RefreshIcon,
    FilterList as FilterIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { ValidationSession, Meeting } from '../../types/validation';
import apiClient from '../../services/api';

interface DashboardStats {
    total_meetings: number;
    pending_validations: number;
    completed_validations: number;
    failed_crm_syncs: number;
}

const ValidationDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [validationSessions, setValidationSessions] = useState<ValidationSession[]>([]);
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        loadData();
    }, [statusFilter]);

    const loadData = async () => {
        try {
            setLoading(true);
            setError(null);

            const [sessionsResponse, statsResponse] = await Promise.all([
                apiClient.getValidationSessions({
                    status: statusFilter === 'all' ? undefined : statusFilter,
                    page: 1,
                    limit: 50,
                }),
                apiClient.getDashboardStats(),
            ]);

            setValidationSessions(sessionsResponse.data.results);
            setStats(statsResponse.data);
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to load validation data');
        } finally {
            setLoading(false);
        }
    };

    const handleViewSession = (sessionId: string) => {
        navigate(`/validation/${sessionId}`);
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'pending':
                return 'warning';
            case 'in_progress':
                return 'info';
            case 'completed':
                return 'success';
            case 'rejected':
                return 'error';
            default:
                return 'default';
        }
    };

    const filteredSessions = validationSessions.filter((session) =>
        session.sales_rep_email.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <Typography>Loading validation dashboard...</Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" component="h1">
                    Validation Dashboard
                </Typography>
                <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={loadData}
                    disabled={loading}
                >
                    Refresh
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            {/* Stats Cards */}
            {stats && (
                <Grid container spacing={3} sx={{ mb: 4 }}>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Total Meetings
                                </Typography>
                                <Typography variant="h4">
                                    {stats.total_meetings}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Pending Validations
                                </Typography>
                                <Typography variant="h4" color="warning.main">
                                    {stats.pending_validations}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Completed Validations
                                </Typography>
                                <Typography variant="h4" color="success.main">
                                    {stats.completed_validations}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom>
                                    Failed CRM Syncs
                                </Typography>
                                <Typography variant="h4" color="error.main">
                                    {stats.failed_crm_syncs}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            {/* Filters */}
            <Box display="flex" gap={2} mb={3}>
                <TextField
                    label="Search by sales rep email"
                    variant="outlined"
                    size="small"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    sx={{ minWidth: 250 }}
                />
                <TextField
                    select
                    label="Status"
                    variant="outlined"
                    size="small"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    sx={{ minWidth: 150 }}
                >
                    <MenuItem value="all">All Statuses</MenuItem>
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="in_progress">In Progress</MenuItem>
                    <MenuItem value="completed">Completed</MenuItem>
                    <MenuItem value="rejected">Rejected</MenuItem>
                </TextField>
            </Box>

            {/* Validation Sessions Table */}
            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Sales Rep</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Started At</TableCell>
                            <TableCell>Completed At</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {filteredSessions.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} align="center">
                                    <Typography color="textSecondary">
                                        No validation sessions found
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            filteredSessions.map((session) => (
                                <TableRow key={session.id}>
                                    <TableCell>{session.sales_rep_email}</TableCell>
                                    <TableCell>
                                        <Chip
                                            label={session.validation_status}
                                            color={getStatusColor(session.validation_status) as any}
                                            size="small"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        {new Date(session.started_at).toLocaleString()}
                                    </TableCell>
                                    <TableCell>
                                        {session.completed_at
                                            ? new Date(session.completed_at).toLocaleString()
                                            : '-'}
                                    </TableCell>
                                    <TableCell>
                                        <Tooltip title="View Session">
                                            <IconButton
                                                onClick={() => handleViewSession(session.id)}
                                                size="small"
                                            >
                                                <VisibilityIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
};

export default ValidationDashboard;