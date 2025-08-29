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
    InputAdornment,
    Pagination,
} from '@mui/material';
import {
    Visibility as VisibilityIcon,
    Refresh as RefreshIcon,
    Search as SearchIcon,
    GetApp as ExportIcon,
    CompareArrows as CompareIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Meeting, ValidationSession, CRMSyncRecord } from '../../types/validation';
import apiClient from '../../services/api';

interface MeetingWithDetails extends Meeting {
    validation_session?: ValidationSession;
    crm_sync_records?: CRMSyncRecord[];
    has_transcript?: boolean;
}

interface MeetingDashboardStats {
    total_meetings: number;
    meetings_with_transcripts: number;
    pending_validations: number;
    completed_validations: number;
    successful_crm_syncs: number;
    failed_crm_syncs: number;
}

const MeetingDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [meetings, setMeetings] = useState<MeetingWithDetails[]>([]);
    const [stats, setStats] = useState<MeetingDashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [validationStatusFilter, setValidationStatusFilter] = useState<string>('all');
    const [crmSyncStatusFilter, setCrmSyncStatusFilter] = useState<string>('all');
    const [searchTerm, setSearchTerm] = useState('');
    const [platformFilter, setPlatformFilter] = useState<string>('all');

    // Pagination
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const itemsPerPage = 20;

    useEffect(() => {
        loadData();
    }, [statusFilter, validationStatusFilter, crmSyncStatusFilter, platformFilter, page]);

    useEffect(() => {
        // Reset to first page when filters change
        if (page !== 1) {
            setPage(1);
        } else {
            loadData();
        }
    }, [searchTerm]);

    const loadData = async () => {
        try {
            setLoading(true);
            setError(null);

            const params: any = {
                page,
                limit: itemsPerPage,
            };

            if (statusFilter !== 'all') params.status = statusFilter;
            if (validationStatusFilter !== 'all') params.validation_status = validationStatusFilter;
            if (crmSyncStatusFilter !== 'all') params.crm_sync_status = crmSyncStatusFilter;
            if (platformFilter !== 'all') params.platform = platformFilter;
            if (searchTerm.trim()) params.search = searchTerm.trim();

            const [meetingsResponse, statsResponse] = await Promise.all([
                apiClient.getMeetingsWithDetails(params),
                apiClient.getMeetingDashboardStats(),
            ]);

            setMeetings(meetingsResponse.data.results);
            setTotalCount(meetingsResponse.data.count);
            setTotalPages(Math.ceil(meetingsResponse.data.count / itemsPerPage));
            setStats(statsResponse.data);
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to load meeting data');
        } finally {
            setLoading(false);
        }
    };

    const handleViewMeeting = (meetingId: string) => {
        navigate(`/meetings/${meetingId}`);
    };

    const handleViewValidation = (sessionId: string) => {
        navigate(`/validation/${sessionId}`);
    };

    const handleCompareTranscripts = (meetingId: string) => {
        navigate(`/meetings/${meetingId}/transcript-comparison`);
    };

    const handleExportTranscript = async (meetingId: string) => {
        try {
            const response = await apiClient.exportMeetingTranscript(meetingId);
            const blob = new Blob([response.data], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `meeting-${meetingId}-transcript.txt`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err: any) {
            setError('Failed to export transcript');
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'scheduled':
                return 'info';
            case 'in_progress':
                return 'warning';
            case 'completed':
                return 'success';
            case 'cancelled':
                return 'error';
            default:
                return 'default';
        }
    };

    const getValidationStatusColor = (status?: string) => {
        if (!status) return 'default';
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

    const getCrmSyncStatusColor = (records?: CRMSyncRecord[]) => {
        if (!records || records.length === 0) return 'default';

        const hasFailure = records.some(record => record.sync_status === 'failed');
        const allCompleted = records.every(record => record.sync_status === 'completed');
        const hasInProgress = records.some(record => record.sync_status === 'in_progress');

        if (hasFailure) return 'error';
        if (allCompleted) return 'success';
        if (hasInProgress) return 'info';
        return 'warning';
    };

    const getCrmSyncStatusText = (records?: CRMSyncRecord[]) => {
        if (!records || records.length === 0) return 'No sync';

        const hasFailure = records.some(record => record.sync_status === 'failed');
        const allCompleted = records.every(record => record.sync_status === 'completed');
        const hasInProgress = records.some(record => record.sync_status === 'in_progress');

        if (hasFailure) return 'Failed';
        if (allCompleted) return 'Completed';
        if (hasInProgress) return 'In Progress';
        return 'Pending';
    };

    const handlePageChange = (event: React.ChangeEvent<unknown>, newPage: number) => {
        setPage(newPage);
    };

    if (loading && meetings.length === 0) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <Typography>Loading meeting dashboard...</Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" component="h1">
                    Meeting Dashboard
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
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    Total Meetings
                                </Typography>
                                <Typography variant="h5">
                                    {stats.total_meetings}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    With Transcripts
                                </Typography>
                                <Typography variant="h5" color="info.main">
                                    {stats.meetings_with_transcripts}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    Pending Validations
                                </Typography>
                                <Typography variant="h5" color="warning.main">
                                    {stats.pending_validations}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    Completed Validations
                                </Typography>
                                <Typography variant="h5" color="success.main">
                                    {stats.completed_validations}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    Successful CRM Syncs
                                </Typography>
                                <Typography variant="h5" color="success.main">
                                    {stats.successful_crm_syncs}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={2}>
                        <Card>
                            <CardContent>
                                <Typography color="textSecondary" gutterBottom variant="body2">
                                    Failed CRM Syncs
                                </Typography>
                                <Typography variant="h5" color="error.main">
                                    {stats.failed_crm_syncs}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            {/* Filters */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} md={3}>
                    <TextField
                        fullWidth
                        label="Search transcripts"
                        variant="outlined"
                        size="small"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon />
                                </InputAdornment>
                            ),
                        }}
                        placeholder="Search meeting content..."
                    />
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                    <TextField
                        select
                        fullWidth
                        label="Meeting Status"
                        variant="outlined"
                        size="small"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <MenuItem value="all">All Statuses</MenuItem>
                        <MenuItem value="scheduled">Scheduled</MenuItem>
                        <MenuItem value="in_progress">In Progress</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="cancelled">Cancelled</MenuItem>
                    </TextField>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                    <TextField
                        select
                        fullWidth
                        label="Validation Status"
                        variant="outlined"
                        size="small"
                        value={validationStatusFilter}
                        onChange={(e) => setValidationStatusFilter(e.target.value)}
                    >
                        <MenuItem value="all">All Validations</MenuItem>
                        <MenuItem value="pending">Pending</MenuItem>
                        <MenuItem value="in_progress">In Progress</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="rejected">Rejected</MenuItem>
                        <MenuItem value="none">No Validation</MenuItem>
                    </TextField>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                    <TextField
                        select
                        fullWidth
                        label="CRM Sync Status"
                        variant="outlined"
                        size="small"
                        value={crmSyncStatusFilter}
                        onChange={(e) => setCrmSyncStatusFilter(e.target.value)}
                    >
                        <MenuItem value="all">All CRM Syncs</MenuItem>
                        <MenuItem value="pending">Pending</MenuItem>
                        <MenuItem value="in_progress">In Progress</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="failed">Failed</MenuItem>
                        <MenuItem value="none">No Sync</MenuItem>
                    </TextField>
                </Grid>
                <Grid item xs={12} sm={6} md={2}>
                    <TextField
                        select
                        fullWidth
                        label="Platform"
                        variant="outlined"
                        size="small"
                        value={platformFilter}
                        onChange={(e) => setPlatformFilter(e.target.value)}
                    >
                        <MenuItem value="all">All Platforms</MenuItem>
                        <MenuItem value="meet">Google Meet</MenuItem>
                        <MenuItem value="teams">Microsoft Teams</MenuItem>
                        <MenuItem value="zoom">Zoom</MenuItem>
                    </TextField>
                </Grid>
            </Grid>

            {/* Results Summary */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="body2" color="textSecondary">
                    Showing {meetings.length} of {totalCount} meetings
                </Typography>
                <Typography variant="body2" color="textSecondary">
                    Page {page} of {totalPages}
                </Typography>
            </Box>

            {/* Meetings Table */}
            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Meeting Title</TableCell>
                            <TableCell>Platform</TableCell>
                            <TableCell>Date & Time</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Validation</TableCell>
                            <TableCell>CRM Sync</TableCell>
                            <TableCell>Transcript</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {meetings.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} align="center">
                                    <Typography color="textSecondary">
                                        No meetings found
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            meetings.map((meeting) => (
                                <TableRow key={meeting.id}>
                                    <TableCell>
                                        <Typography variant="body2" fontWeight="medium">
                                            {meeting.title}
                                        </Typography>
                                        <Typography variant="caption" color="textSecondary">
                                            {meeting.attendees.length} attendees
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Chip
                                            label={meeting.platform.toUpperCase()}
                                            size="small"
                                            variant="outlined"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2">
                                            {new Date(meeting.start_time).toLocaleDateString()}
                                        </Typography>
                                        <Typography variant="caption" color="textSecondary">
                                            {new Date(meeting.start_time).toLocaleTimeString()} - {' '}
                                            {new Date(meeting.end_time).toLocaleTimeString()}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Chip
                                            label={meeting.status}
                                            color={getStatusColor(meeting.status) as any}
                                            size="small"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        {meeting.validation_session ? (
                                            <Chip
                                                label={meeting.validation_session.validation_status}
                                                color={getValidationStatusColor(meeting.validation_session.validation_status) as any}
                                                size="small"
                                            />
                                        ) : (
                                            <Chip
                                                label="No validation"
                                                color="default"
                                                size="small"
                                                variant="outlined"
                                            />
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Chip
                                            label={getCrmSyncStatusText(meeting.crm_sync_records)}
                                            color={getCrmSyncStatusColor(meeting.crm_sync_records) as any}
                                            size="small"
                                        />
                                    </TableCell>
                                    <TableCell>
                                        {meeting.has_transcript ? (
                                            <Chip
                                                label="Available"
                                                color="success"
                                                size="small"
                                            />
                                        ) : (
                                            <Chip
                                                label="Not available"
                                                color="default"
                                                size="small"
                                                variant="outlined"
                                            />
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Box display="flex" gap={1}>
                                            <Tooltip title="View Meeting Details">
                                                <IconButton
                                                    onClick={() => handleViewMeeting(meeting.id)}
                                                    size="small"
                                                >
                                                    <VisibilityIcon />
                                                </IconButton>
                                            </Tooltip>
                                            {meeting.validation_session && (
                                                <Tooltip title="View Validation Session">
                                                    <IconButton
                                                        onClick={() => handleViewValidation(meeting.validation_session!.id)}
                                                        size="small"
                                                    >
                                                        <VisibilityIcon color="primary" />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                            {meeting.has_transcript && (
                                                <>
                                                    <Tooltip title="Compare Transcripts">
                                                        <IconButton
                                                            onClick={() => handleCompareTranscripts(meeting.id)}
                                                            size="small"
                                                        >
                                                            <CompareIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                    <Tooltip title="Export Transcript">
                                                        <IconButton
                                                            onClick={() => handleExportTranscript(meeting.id)}
                                                            size="small"
                                                        >
                                                            <ExportIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                </>
                                            )}
                                        </Box>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Pagination */}
            {totalPages > 1 && (
                <Box display="flex" justifyContent="center" mt={3}>
                    <Pagination
                        count={totalPages}
                        page={page}
                        onChange={handlePageChange}
                        color="primary"
                        showFirstButton
                        showLastButton
                    />
                </Box>
            )}
        </Box>
    );
};

export default MeetingDashboard;