import React, { useState, useEffect } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    Button,
    Alert,
    Grid,
    Paper,
    Chip,
    CircularProgress,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { ValidationSession as ValidationSessionType, DraftSummary, ValidationFormData } from '../../types/validation';
import apiClient from '../../services/api';
import ValidationForm from '../../components/ValidationForm/ValidationForm';
import TranscriptComparison from '../../components/TranscriptComparison/TranscriptComparison';

const ValidationSession: React.FC = () => {
    const { sessionId } = useParams<{ sessionId: string }>();
    const navigate = useNavigate();

    const [session, setSession] = useState<ValidationSessionType | null>(null);
    const [draftSummary, setDraftSummary] = useState<DraftSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [formData, setFormData] = useState<ValidationFormData>({
        summary_approved: false,
        summary_edits: '',
        next_steps: '',
        crm_updates_approved: false,
        crm_updates_edits: {},
        additional_notes: '',
    });

    useEffect(() => {
        if (sessionId) {
            loadSessionData();
        }
    }, [sessionId]);

    const loadSessionData = async () => {
        try {
            setLoading(true);
            setError(null);

            const sessionResponse = await apiClient.getValidationSession(sessionId!);
            const session = sessionResponse.data;
            setSession(session);

            const summaryResponse = await apiClient.getDraftSummary(session.draft_summary);
            setDraftSummary(summaryResponse.data);

            // Initialize form data with existing responses
            setFormData({
                summary_approved: session.rep_responses?.summary_approved || false,
                summary_edits: session.rep_responses?.summary_edits || '',
                next_steps: session.rep_responses?.next_steps || '',
                crm_updates_approved: session.rep_responses?.crm_updates_approved || false,
                crm_updates_edits: session.rep_responses?.crm_updates_edits || {},
                additional_notes: session.rep_responses?.additional_notes || '',
            });
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to load validation session');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            setError(null);
            setSuccess(null);

            await apiClient.updateValidationSession(sessionId!, formData);
            setSuccess('Changes saved successfully');
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to save changes');
        } finally {
            setSaving(false);
        }
    };

    const handleComplete = async () => {
        try {
            setSaving(true);
            setError(null);
            setSuccess(null);

            await apiClient.completeValidationSession(sessionId!, formData);
            setSuccess('Validation session completed successfully');

            // Reload session data to show updated status
            setTimeout(() => {
                loadSessionData();
            }, 1000);
        } catch (err: any) {
            setError(err.response?.data?.message || 'Failed to complete validation session');
        } finally {
            setSaving(false);
        }
    };

    const handleFormChange = (field: keyof ValidationFormData, value: any) => {
        setFormData(prev => ({
            ...prev,
            [field]: value,
        }));
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (!session || !draftSummary) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">
                    Validation session not found
                </Alert>
            </Box>
        );
    }

    const isCompleted = session.validation_status === 'completed';

    return (
        <Box sx={{ p: 3 }}>
            <Box display="flex" alignItems="center" mb={3}>
                <Button
                    startIcon={<ArrowBackIcon />}
                    onClick={() => navigate('/validation')}
                    sx={{ mr: 2 }}
                >
                    Back to Dashboard
                </Button>
                <Typography variant="h4" component="h1">
                    Validation Session
                </Typography>
                <Chip
                    label={session.validation_status}
                    color={session.validation_status === 'completed' ? 'success' : 'warning'}
                    sx={{ ml: 2 }}
                />
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            {success && (
                <Alert severity="success" sx={{ mb: 3 }}>
                    {success}
                </Alert>
            )}

            <Grid container spacing={3}>
                {/* AI Generated Summary */}
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                AI Generated Summary
                            </Typography>
                            <Paper sx={{ p: 2, bgcolor: 'grey.50', mb: 2 }}>
                                <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
                                    {draftSummary.ai_generated_summary}
                                </Typography>
                            </Paper>

                            <Typography variant="subtitle2" gutterBottom>
                                Confidence Score: {(draftSummary.confidence_score * 100).toFixed(1)}%
                            </Typography>

                            {draftSummary.extracted_action_items.length > 0 && (
                                <>
                                    <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                                        Action Items:
                                    </Typography>
                                    {draftSummary.extracted_action_items.map((item, index) => (
                                        <Chip
                                            key={index}
                                            label={item.description}
                                            size="small"
                                            sx={{ mr: 1, mb: 1 }}
                                        />
                                    ))}
                                </>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* Validation Form */}
                <Grid item xs={12}>
                    <ValidationForm
                        draftSummary={draftSummary}
                        formData={formData}
                        onFormChange={handleFormChange}
                        onSave={handleSave}
                        onComplete={handleComplete}
                        saving={saving}
                        isCompleted={isCompleted}
                    />
                </Grid>

                {/* Transcript Comparison - Show only if validation is completed */}
                {isCompleted && (
                    <Grid item xs={12}>
                        <TranscriptComparison
                            draftSummary={draftSummary}
                            validationSession={session}
                        />
                    </Grid>
                )}
            </Grid>
        </Box>
    );
};

export default ValidationSession;