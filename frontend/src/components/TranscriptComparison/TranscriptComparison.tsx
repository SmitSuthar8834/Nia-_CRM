import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Tabs,
    Tab,
    Paper,
    Button,
    Chip,
    Grid,
    Divider,
} from '@mui/material';
import {
    Download as DownloadIcon,
    Compare as CompareIcon,
} from '@mui/icons-material';
import { DraftSummary, ValidationSession } from '../../types/validation';

interface TranscriptComparisonProps {
    draftSummary: DraftSummary;
    validationSession: ValidationSession;
}

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`transcript-tabpanel-${index}`}
            aria-labelledby={`transcript-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
        </div>
    );
};

const TranscriptComparison: React.FC<TranscriptComparisonProps> = ({
    draftSummary,
    validationSession,
}) => {
    const [tabValue, setTabValue] = useState(0);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
    };

    const handleExport = (type: 'draft' | 'validated') => {
        const content = type === 'draft'
            ? draftSummary.ai_generated_summary
            : validationSession.validated_summary;

        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}-summary-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const renderActionItems = (items: any[]) => {
        if (!items || items.length === 0) {
            return <Typography color="textSecondary">No action items</Typography>;
        }

        return (
            <Box>
                {items.map((item, index) => (
                    <Chip
                        key={index}
                        label={typeof item === 'string' ? item : item.description}
                        size="small"
                        sx={{ mr: 1, mb: 1 }}
                    />
                ))}
            </Box>
        );
    };

    const renderSummarySection = (
        title: string,
        summary: string,
        actionItems: any[],
        confidence?: number,
        isValidated = false
    ) => (
        <Paper sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">{title}</Typography>
                <Box display="flex" gap={1} alignItems="center">
                    {confidence !== undefined && (
                        <Chip
                            label={`Confidence: ${(confidence * 100).toFixed(1)}%`}
                            size="small"
                            color={confidence > 0.8 ? 'success' : confidence > 0.6 ? 'warning' : 'error'}
                        />
                    )}
                    <Button
                        size="small"
                        startIcon={<DownloadIcon />}
                        onClick={() => handleExport(isValidated ? 'validated' : 'draft')}
                    >
                        Export
                    </Button>
                </Box>
            </Box>

            <Paper sx={{ p: 2, bgcolor: 'grey.50', mb: 2 }}>
                <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
                    {summary || 'No summary available'}
                </Typography>
            </Paper>

            <Typography variant="subtitle2" gutterBottom>
                Action Items:
            </Typography>
            {renderActionItems(actionItems)}
        </Paper>
    );

    const renderSideBySideComparison = () => (
        <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom color="primary">
                    AI Generated (Draft)
                </Typography>
                {renderSummarySection(
                    'Draft Summary',
                    draftSummary.ai_generated_summary,
                    draftSummary.extracted_action_items,
                    draftSummary.confidence_score
                )}
            </Grid>
            <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom color="success.main">
                    Human Validated (Final)
                </Typography>
                {renderSummarySection(
                    'Validated Summary',
                    validationSession.validated_summary,
                    validationSession.rep_responses?.action_items || [],
                    undefined,
                    true
                )}
            </Grid>
        </Grid>
    );

    return (
        <Card>
            <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h5">
                        Transcript Comparison
                    </Typography>
                    <Chip
                        icon={<CompareIcon />}
                        label={validationSession.validation_status}
                        color={validationSession.validation_status === 'completed' ? 'success' : 'warning'}
                    />
                </Box>

                <Tabs value={tabValue} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tab label="Draft Summary" />
                    <Tab label="Validated Summary" />
                    <Tab label="Side-by-Side" />
                </Tabs>

                <TabPanel value={tabValue} index={0}>
                    {renderSummarySection(
                        'AI Generated Summary',
                        draftSummary.ai_generated_summary,
                        draftSummary.extracted_action_items,
                        draftSummary.confidence_score
                    )}

                    <Divider sx={{ my: 3 }} />

                    <Typography variant="h6" gutterBottom>
                        Suggested Next Steps
                    </Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                        <Typography variant="body2">
                            {draftSummary.suggested_next_steps || 'No next steps suggested'}
                        </Typography>
                    </Paper>

                    {draftSummary.suggested_crm_updates &&
                        Object.keys(draftSummary.suggested_crm_updates).length > 0 && (
                            <>
                                <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                                    Suggested CRM Updates
                                </Typography>
                                <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                                    <pre style={{ fontSize: '0.875rem', margin: 0, whiteSpace: 'pre-wrap' }}>
                                        {JSON.stringify(draftSummary.suggested_crm_updates, null, 2)}
                                    </pre>
                                </Paper>
                            </>
                        )}
                </TabPanel>

                <TabPanel value={tabValue} index={1}>
                    {renderSummarySection(
                        'Human Validated Summary',
                        validationSession.validated_summary,
                        validationSession.rep_responses?.action_items || [],
                        undefined,
                        true
                    )}

                    <Divider sx={{ my: 3 }} />

                    <Typography variant="h6" gutterBottom>
                        Validated Next Steps
                    </Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                        <Typography variant="body2">
                            {validationSession.rep_responses?.next_steps || 'No next steps provided'}
                        </Typography>
                    </Paper>

                    {validationSession.approved_crm_updates &&
                        Object.keys(validationSession.approved_crm_updates).length > 0 && (
                            <>
                                <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                                    Approved CRM Updates
                                </Typography>
                                <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                                    <pre style={{ fontSize: '0.875rem', margin: 0, whiteSpace: 'pre-wrap' }}>
                                        {JSON.stringify(validationSession.approved_crm_updates, null, 2)}
                                    </pre>
                                </Paper>
                            </>
                        )}

                    {validationSession.rep_responses?.additional_notes && (
                        <>
                            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                                Additional Notes
                            </Typography>
                            <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                                <Typography variant="body2">
                                    {validationSession.rep_responses.additional_notes}
                                </Typography>
                            </Paper>
                        </>
                    )}
                </TabPanel>

                <TabPanel value={tabValue} index={2}>
                    {renderSideBySideComparison()}
                </TabPanel>
            </CardContent>
        </Card>
    );
};

export default TranscriptComparison;