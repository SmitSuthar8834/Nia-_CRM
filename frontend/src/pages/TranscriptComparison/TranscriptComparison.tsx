import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    Grid,
    Button,
    Alert,
    Chip,
    Divider,
    IconButton,
    Tooltip,
    Paper,
    Switch,
    FormControlLabel,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    GetApp as ExportIcon,
    Refresh as RefreshIcon,
    Visibility as VisibilityIcon,
    VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { Meeting, CallBotSession, ValidationSession } from '../../types/validation';
import apiClient from '../../services/api';

interface TranscriptData {
    meeting: Meeting;
    callBotSession: CallBotSession;
    validationSession?: ValidationSession;
    rawTranscript: string;
    validatedTranscript?: string;
}

interface DiffSegment {
    type: 'unchanged' | 'added' | 'removed' | 'modified';
    rawText: string;
    validatedText?: string;
    lineNumber: number;
}

const TranscriptComparison: React.FC = () => {
    const navigate = useNavigate();
    const { meetingId } = useParams<{ meetingId: string }>();
    const [transcriptData, setTranscriptData] = useState<TranscriptData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showDiffOnly, setShowDiffOnly] = useState(false);
    const [diffSegments, setDiffSegments] = useState<DiffSegment[]>([]);

    useEffect(() => {
        if (meetingId) {
            loadTranscriptData();
        }
    }, [meetingId]);

    useEffect(() => {
        if (transcriptData) {
            generateDiffSegments();
        }
    }, [transcriptData]);

    const loadTranscriptData = async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await apiClient.getMeetingTranscriptComparison(meetingId!);
            setTranscriptData(response.data);
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to load transcript data');
        } finally {
            setLoading(false);
        }
    };

    const generateDiffSegments = () => {
        if (!transcriptData) return;

        const rawLines = transcriptData.rawTranscript.split('\n');
        const validatedLines = transcriptData.validatedTranscript?.split('\n') || [];
        const segments: DiffSegment[] = [];

        // Simple diff algorithm - in a real implementation, you'd use a more sophisticated diff library
        const maxLines = Math.max(rawLines.length, validatedLines.length);

        for (let i = 0; i < maxLines; i++) {
            const rawLine = rawLines[i] || '';
            const validatedLine = validatedLines[i] || '';

            if (rawLine === validatedLine) {
                segments.push({
                    type: 'unchanged',
                    rawText: rawLine,
                    validatedText: validatedLine,
                    lineNumber: i + 1,
                });
            } else if (rawLine && !validatedLine) {
                segments.push({
                    type: 'removed',
                    rawText: rawLine,
                    validatedText: '',
                    lineNumber: i + 1,
                });
            } else if (!rawLine && validatedLine) {
                segments.push({
                    type: 'added',
                    rawText: '',
                    validatedText: validatedLine,
                    lineNumber: i + 1,
                });
            } else {
                segments.push({
                    type: 'modified',
                    rawText: rawLine,
                    validatedText: validatedLine,
                    lineNumber: i + 1,
                });
            }
        }

        setDiffSegments(segments);
    };

    const handleExportComparison = async () => {
        if (!transcriptData) return;

        try {
            const comparisonText = generateComparisonText();
            const blob = new Blob([comparisonText], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `meeting-${meetingId}-transcript-comparison.txt`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err: any) {
            setError('Failed to export comparison');
        }
    };

    const generateComparisonText = (): string => {
        if (!transcriptData) return '';

        let text = `Meeting Transcript Comparison\n`;
        text += `Meeting: ${transcriptData.meeting.title}\n`;
        text += `Date: ${new Date(transcriptData.meeting.start_time).toLocaleString()}\n`;
        text += `Platform: ${transcriptData.meeting.platform.toUpperCase()}\n\n`;

        text += `=== RAW TRANSCRIPT ===\n`;
        text += transcriptData.rawTranscript;
        text += `\n\n=== VALIDATED TRANSCRIPT ===\n`;
        text += transcriptData.validatedTranscript || 'No validated transcript available';

        if (diffSegments.length > 0) {
            text += `\n\n=== CHANGES SUMMARY ===\n`;
            const changes = diffSegments.filter(segment => segment.type !== 'unchanged');
            changes.forEach((segment, index) => {
                text += `${index + 1}. Line ${segment.lineNumber} (${segment.type}):\n`;
                if (segment.type === 'removed') {
                    text += `  - Removed: "${segment.rawText}"\n`;
                } else if (segment.type === 'added') {
                    text += `  + Added: "${segment.validatedText}"\n`;
                } else if (segment.type === 'modified') {
                    text += `  - Original: "${segment.rawText}"\n`;
                    text += `  + Modified: "${segment.validatedText}"\n`;
                }
                text += '\n';
            });
        }

        return text;
    };

    const getSegmentBackgroundColor = (type: string) => {
        switch (type) {
            case 'added':
                return '#e8f5e8';
            case 'removed':
                return '#ffeaea';
            case 'modified':
                return '#fff3cd';
            default:
                return 'transparent';
        }
    };

    const getSegmentBorderColor = (type: string) => {
        switch (type) {
            case 'added':
                return '#4caf50';
            case 'removed':
                return '#f44336';
            case 'modified':
                return '#ff9800';
            default:
                return 'transparent';
        }
    };

    const filteredSegments = showDiffOnly
        ? diffSegments.filter(segment => segment.type !== 'unchanged')
        : diffSegments;

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <Typography>Loading transcript comparison...</Typography>
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
                <Button
                    variant="outlined"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => navigate('/meetings')}
                >
                    Back to Meetings
                </Button>
            </Box>
        );
    }

    if (!transcriptData) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="info" sx={{ mb: 3 }}>
                    No transcript data available for this meeting.
                </Alert>
                <Button
                    variant="outlined"
                    startIcon={<ArrowBackIcon />}
                    onClick={() => navigate('/meetings')}
                >
                    Back to Meetings
                </Button>
            </Box>
        );
    }

    const changesCount = diffSegments.filter(segment => segment.type !== 'unchanged').length;

    return (
        <Box sx={{ p: 3 }}>
            {/* Header */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Box display="flex" alignItems="center" gap={2}>
                    <IconButton onClick={() => navigate('/meetings')}>
                        <ArrowBackIcon />
                    </IconButton>
                    <Typography variant="h4" component="h1">
                        Transcript Comparison
                    </Typography>
                </Box>
                <Box display="flex" gap={1}>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon />}
                        onClick={loadTranscriptData}
                        disabled={loading}
                    >
                        Refresh
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<ExportIcon />}
                        onClick={handleExportComparison}
                    >
                        Export Comparison
                    </Button>
                </Box>
            </Box>

            {/* Meeting Info */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Grid container spacing={3}>
                        <Grid item xs={12} md={6}>
                            <Typography variant="h6" gutterBottom>
                                {transcriptData.meeting.title}
                            </Typography>
                            <Typography variant="body2" color="textSecondary" gutterBottom>
                                {new Date(transcriptData.meeting.start_time).toLocaleString()} - {' '}
                                {new Date(transcriptData.meeting.end_time).toLocaleString()}
                            </Typography>
                            <Chip
                                label={transcriptData.meeting.platform.toUpperCase()}
                                size="small"
                                variant="outlined"
                            />
                        </Grid>
                        <Grid item xs={12} md={6}>
                            <Box display="flex" gap={2} flexWrap="wrap">
                                <Chip
                                    label={`${changesCount} changes`}
                                    color={changesCount > 0 ? 'warning' : 'success'}
                                    size="small"
                                />
                                {transcriptData.validationSession && (
                                    <Chip
                                        label={`Validation: ${transcriptData.validationSession.validation_status}`}
                                        color="info"
                                        size="small"
                                    />
                                )}
                                <Chip
                                    label={`${diffSegments.length} total lines`}
                                    variant="outlined"
                                    size="small"
                                />
                            </Box>
                        </Grid>
                    </Grid>
                </CardContent>
            </Card>

            {/* Controls */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <FormControlLabel
                    control={
                        <Switch
                            checked={showDiffOnly}
                            onChange={(e) => setShowDiffOnly(e.target.checked)}
                        />
                    }
                    label="Show changes only"
                />
                <Box display="flex" gap={2} alignItems="center">
                    <Box display="flex" alignItems="center" gap={1}>
                        <Box
                            sx={{
                                width: 16,
                                height: 16,
                                backgroundColor: '#e8f5e8',
                                border: '1px solid #4caf50',
                            }}
                        />
                        <Typography variant="caption">Added</Typography>
                    </Box>
                    <Box display="flex" alignItems="center" gap={1}>
                        <Box
                            sx={{
                                width: 16,
                                height: 16,
                                backgroundColor: '#ffeaea',
                                border: '1px solid #f44336',
                            }}
                        />
                        <Typography variant="caption">Removed</Typography>
                    </Box>
                    <Box display="flex" alignItems="center" gap={1}>
                        <Box
                            sx={{
                                width: 16,
                                height: 16,
                                backgroundColor: '#fff3cd',
                                border: '1px solid #ff9800',
                            }}
                        />
                        <Typography variant="caption">Modified</Typography>
                    </Box>
                </Box>
            </Box>

            {/* Comparison View */}
            <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2, height: '70vh', overflow: 'auto' }}>
                        <Typography variant="h6" gutterBottom>
                            Raw Transcript
                        </Typography>
                        <Divider sx={{ mb: 2 }} />
                        {filteredSegments.map((segment, index) => (
                            <Box
                                key={index}
                                sx={{
                                    p: 1,
                                    mb: 1,
                                    backgroundColor: getSegmentBackgroundColor(segment.type),
                                    borderLeft: `3px solid ${getSegmentBorderColor(segment.type)}`,
                                    borderRadius: 1,
                                }}
                            >
                                <Typography
                                    variant="caption"
                                    color="textSecondary"
                                    display="block"
                                    gutterBottom
                                >
                                    Line {segment.lineNumber}
                                </Typography>
                                <Typography
                                    variant="body2"
                                    sx={{
                                        fontFamily: 'monospace',
                                        whiteSpace: 'pre-wrap',
                                        textDecoration: segment.type === 'removed' ? 'line-through' : 'none',
                                    }}
                                >
                                    {segment.rawText || <em>(empty line)</em>}
                                </Typography>
                            </Box>
                        ))}
                    </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2, height: '70vh', overflow: 'auto' }}>
                        <Typography variant="h6" gutterBottom>
                            Validated Transcript
                        </Typography>
                        <Divider sx={{ mb: 2 }} />
                        {transcriptData.validatedTranscript ? (
                            filteredSegments.map((segment, index) => (
                                <Box
                                    key={index}
                                    sx={{
                                        p: 1,
                                        mb: 1,
                                        backgroundColor: getSegmentBackgroundColor(segment.type),
                                        borderLeft: `3px solid ${getSegmentBorderColor(segment.type)}`,
                                        borderRadius: 1,
                                    }}
                                >
                                    <Typography
                                        variant="caption"
                                        color="textSecondary"
                                        display="block"
                                        gutterBottom
                                    >
                                        Line {segment.lineNumber}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontFamily: 'monospace',
                                            whiteSpace: 'pre-wrap',
                                            fontWeight: segment.type === 'added' || segment.type === 'modified' ? 'bold' : 'normal',
                                        }}
                                    >
                                        {segment.validatedText || <em>(empty line)</em>}
                                    </Typography>
                                </Box>
                            ))
                        ) : (
                            <Alert severity="info">
                                No validated transcript available. The meeting may not have gone through validation yet.
                            </Alert>
                        )}
                    </Paper>
                </Grid>
            </Grid>

            {/* Summary */}
            {changesCount > 0 && (
                <Card sx={{ mt: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            Changes Summary
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={4}>
                                <Box textAlign="center">
                                    <Typography variant="h4" color="success.main">
                                        {diffSegments.filter(s => s.type === 'added').length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Lines Added
                                    </Typography>
                                </Box>
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Box textAlign="center">
                                    <Typography variant="h4" color="error.main">
                                        {diffSegments.filter(s => s.type === 'removed').length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Lines Removed
                                    </Typography>
                                </Box>
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Box textAlign="center">
                                    <Typography variant="h4" color="warning.main">
                                        {diffSegments.filter(s => s.type === 'modified').length}
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                        Lines Modified
                                    </Typography>
                                </Box>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}
        </Box>
    );
};

export default TranscriptComparison;