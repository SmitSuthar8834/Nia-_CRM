import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    TextField,
    FormControlLabel,
    Checkbox,
    Button,
    Divider,
    Alert,
    Chip,
    Paper,
    Grid,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    IconButton,
    Radio,
    RadioGroup,
    FormControl,
    FormLabel,
    FormHelperText,
    Rating,
    Select,
    MenuItem,
    InputLabel,
} from '@mui/material';
import {
    Edit as EditIcon,
    Save as SaveIcon,
    Cancel as CancelIcon,
    Add as AddIcon,
    Delete as DeleteIcon,
    CheckCircle as CheckCircleIcon,
    Cancel as CancelIcon2,
} from '@mui/icons-material';
import { DraftSummary, ValidationFormData, ActionItem, ValidationQuestion } from '../../types/validation';

interface ValidationFormProps {
    draftSummary: DraftSummary;
    formData: ValidationFormData;
    validationQuestions?: ValidationQuestion[];
    onFormChange: (field: keyof ValidationFormData, value: any) => void;
    onQuestionResponse: (questionId: string, response: any) => void;
    onSave: () => void;
    onComplete: () => void;
    saving: boolean;
    isCompleted: boolean;
    questionResponses?: Record<string, any>;
}

const ValidationForm: React.FC<ValidationFormProps> = ({
    draftSummary,
    formData,
    validationQuestions = [],
    onFormChange,
    onQuestionResponse,
    onSave,
    onComplete,
    saving,
    isCompleted,
    questionResponses = {},
}) => {
    const [editingSummary, setEditingSummary] = useState(false);
    const [editedSummary, setEditedSummary] = useState(draftSummary.ai_generated_summary);
    const [actionItemDialogOpen, setActionItemDialogOpen] = useState(false);
    const [newActionItem, setNewActionItem] = useState({ description: '', assignee: '', due_date: '' });
    const [editedActionItems, setEditedActionItems] = useState<ActionItem[]>(draftSummary.extracted_action_items);
    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

    const handleSummaryEdit = () => {
        if (editingSummary) {
            // Save the edited summary
            onFormChange('summary_edits', editedSummary);
            onFormChange('summary_approved', false);
        }
        setEditingSummary(!editingSummary);
    };

    const handleCancelSummaryEdit = () => {
        setEditedSummary(draftSummary.ai_generated_summary);
        setEditingSummary(false);
    };

    const handleAddActionItem = () => {
        if (newActionItem.description.trim()) {
            const actionItem: ActionItem = {
                id: `new-${Date.now()}`,
                description: newActionItem.description,
                assignee: newActionItem.assignee,
                due_date: newActionItem.due_date || undefined,
                status: 'pending',
            };
            setEditedActionItems([...editedActionItems, actionItem]);
            setNewActionItem({ description: '', assignee: '', due_date: '' });
            setActionItemDialogOpen(false);
        }
    };

    const handleRemoveActionItem = (itemId: string) => {
        setEditedActionItems(editedActionItems.filter(item => item.id !== itemId));
    };

    const validateQuestion = (question: ValidationQuestion, value: any): string | null => {
        if (question.required && (value === undefined || value === null || value === '')) {
            return 'This field is required';
        }

        if (question.type === 'text' || question.type === 'text_editing') {
            const stringValue = String(value || '');
            if (question.validation?.minLength && stringValue.length < question.validation.minLength) {
                return `Minimum length is ${question.validation.minLength} characters`;
            }
            if (question.validation?.maxLength && stringValue.length > question.validation.maxLength) {
                return `Maximum length is ${question.validation.maxLength} characters`;
            }
            if (question.validation?.pattern && !new RegExp(question.validation.pattern).test(stringValue)) {
                return 'Invalid format';
            }
        }

        return null;
    };

    const validateAllQuestions = (): boolean => {
        const errors: Record<string, string> = {};
        let isValid = true;

        validationQuestions.forEach(question => {
            const value = questionResponses[question.id];
            const error = validateQuestion(question, value);
            if (error) {
                errors[question.id] = error;
                isValid = false;
            }
        });

        // Validate required form fields
        if (!formData.next_steps.trim()) {
            errors['next_steps'] = 'Next steps are required';
            isValid = false;
        }

        setValidationErrors(errors);
        return isValid;
    };

    const handleQuestionResponse = (questionId: string, response: any) => {
        onQuestionResponse(questionId, response);

        // Clear validation error for this question
        if (validationErrors[questionId]) {
            setValidationErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[questionId];
                return newErrors;
            });
        }
    };

    const renderQuestion = (question: ValidationQuestion) => {
        const value = questionResponses[question.id] || question.defaultValue;
        const error = validationErrors[question.id];

        switch (question.type) {
            case 'text':
                return (
                    <TextField
                        key={question.id}
                        fullWidth
                        label={question.question}
                        value={value || ''}
                        onChange={(e) => handleQuestionResponse(question.id, e.target.value)}
                        disabled={isCompleted}
                        required={question.required}
                        error={!!error}
                        helperText={error || question.helperText}
                        margin="normal"
                    />
                );

            case 'text_editing':
                return (
                    <TextField
                        key={question.id}
                        fullWidth
                        multiline
                        rows={4}
                        label={question.question}
                        value={value || ''}
                        onChange={(e) => handleQuestionResponse(question.id, e.target.value)}
                        disabled={isCompleted}
                        required={question.required}
                        error={!!error}
                        helperText={error || question.helperText}
                        margin="normal"
                    />
                );

            case 'boolean':
                return (
                    <FormControl key={question.id} error={!!error} margin="normal">
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={value === true}
                                    onChange={(e) => handleQuestionResponse(question.id, e.target.checked)}
                                    disabled={isCompleted}
                                />
                            }
                            label={question.question}
                        />
                        {error && <FormHelperText>{error}</FormHelperText>}
                        {question.helperText && !error && <FormHelperText>{question.helperText}</FormHelperText>}
                    </FormControl>
                );

            case 'confirmation':
                return (
                    <FormControl key={question.id} error={!!error} margin="normal">
                        <FormLabel component="legend">{question.question}</FormLabel>
                        <RadioGroup
                            value={value || ''}
                            onChange={(e) => handleQuestionResponse(question.id, e.target.value)}
                        >
                            <FormControlLabel
                                value="confirmed"
                                control={<Radio />}
                                label={<Box display="flex" alignItems="center"><CheckCircleIcon color="success" sx={{ mr: 1 }} />Confirmed</Box>}
                                disabled={isCompleted}
                            />
                            <FormControlLabel
                                value="rejected"
                                control={<Radio />}
                                label={<Box display="flex" alignItems="center"><CancelIcon2 color="error" sx={{ mr: 1 }} />Rejected</Box>}
                                disabled={isCompleted}
                            />
                        </RadioGroup>
                        {error && <FormHelperText>{error}</FormHelperText>}
                        {question.helperText && !error && <FormHelperText>{question.helperText}</FormHelperText>}
                    </FormControl>
                );

            case 'multiple_choice':
                return (
                    <FormControl key={question.id} fullWidth error={!!error} margin="normal">
                        <InputLabel>{question.question}</InputLabel>
                        <Select
                            value={value || ''}
                            onChange={(e) => handleQuestionResponse(question.id, e.target.value)}
                            disabled={isCompleted}
                            label={question.question}
                        >
                            {question.options?.map((option) => (
                                <MenuItem key={option} value={option}>
                                    {option}
                                </MenuItem>
                            ))}
                        </Select>
                        {error && <FormHelperText>{error}</FormHelperText>}
                        {question.helperText && !error && <FormHelperText>{question.helperText}</FormHelperText>}
                    </FormControl>
                );

            case 'rating':
                return (
                    <FormControl key={question.id} error={!!error} margin="normal">
                        <FormLabel component="legend">{question.question}</FormLabel>
                        <Rating
                            value={value || 0}
                            onChange={(_, newValue) => handleQuestionResponse(question.id, newValue)}
                            disabled={isCompleted}
                            max={5}
                            size="large"
                        />
                        {error && <FormHelperText>{error}</FormHelperText>}
                        {question.helperText && !error && <FormHelperText>{question.helperText}</FormHelperText>}
                    </FormControl>
                );

            default:
                return null;
        }
    };

    const isFormValid = () => {
        return validateAllQuestions();
    };

    return (
        <Box>
            {/* AI Generated Summary Section */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography variant="h6">
                            AI Generated Summary
                        </Typography>
                        {!isCompleted && (
                            <Box>
                                <Button
                                    size="small"
                                    startIcon={editingSummary ? <SaveIcon /> : <EditIcon />}
                                    onClick={handleSummaryEdit}
                                    disabled={saving}
                                >
                                    {editingSummary ? 'Save Edit' : 'Edit Summary'}
                                </Button>
                                {editingSummary && (
                                    <Button
                                        size="small"
                                        startIcon={<CancelIcon />}
                                        onClick={handleCancelSummaryEdit}
                                        sx={{ ml: 1 }}
                                    >
                                        Cancel
                                    </Button>
                                )}
                            </Box>
                        )}
                    </Box>

                    {editingSummary ? (
                        <TextField
                            fullWidth
                            multiline
                            rows={6}
                            value={editedSummary}
                            onChange={(e) => setEditedSummary(e.target.value)}
                            disabled={isCompleted}
                        />
                    ) : (
                        <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                            <Typography variant="body2" style={{ whiteSpace: 'pre-wrap' }}>
                                {editedSummary}
                            </Typography>
                        </Paper>
                    )}

                    <Box mt={2} display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="caption" color="textSecondary">
                            Confidence Score: {(draftSummary.confidence_score * 100).toFixed(1)}%
                        </Typography>
                        {!editingSummary && (
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={formData.summary_approved}
                                        onChange={(e) => onFormChange('summary_approved', e.target.checked)}
                                        disabled={isCompleted}
                                    />
                                }
                                label="Summary is accurate"
                            />
                        )}
                    </Box>
                </CardContent>
            </Card>

            {/* Action Items Section */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography variant="h6">
                            Action Items
                        </Typography>
                        {!isCompleted && (
                            <Button
                                size="small"
                                startIcon={<AddIcon />}
                                onClick={() => setActionItemDialogOpen(true)}
                            >
                                Add Item
                            </Button>
                        )}
                    </Box>

                    {editedActionItems.length === 0 ? (
                        <Typography color="textSecondary" variant="body2">
                            No action items identified
                        </Typography>
                    ) : (
                        <List>
                            {editedActionItems.map((item) => (
                                <ListItem key={item.id} divider>
                                    <ListItemText
                                        primary={item.description}
                                        secondary={
                                            <Box>
                                                {item.assignee && (
                                                    <Chip label={`Assigned: ${item.assignee}`} size="small" sx={{ mr: 1 }} />
                                                )}
                                                {item.due_date && (
                                                    <Chip label={`Due: ${item.due_date}`} size="small" />
                                                )}
                                            </Box>
                                        }
                                    />
                                    {!isCompleted && (
                                        <ListItemSecondaryAction>
                                            <IconButton
                                                edge="end"
                                                onClick={() => handleRemoveActionItem(item.id)}
                                                size="small"
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </ListItemSecondaryAction>
                                    )}
                                </ListItem>
                            ))}
                        </List>
                    )}
                </CardContent>
            </Card>

            {/* Dynamic Validation Questions */}
            {validationQuestions.length > 0 && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" gutterBottom>
                            Validation Questions
                        </Typography>
                        <Box>
                            {validationQuestions.map(question => (
                                <Box key={question.id} sx={{ mb: 2 }}>
                                    {renderQuestion(question)}
                                </Box>
                            ))}
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Validation Form */}
            <Card>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        Validation & Next Steps
                    </Typography>

                    <Grid container spacing={3}>
                        <Grid item xs={12}>
                            <TextField
                                fullWidth
                                multiline
                                rows={3}
                                label="Next steps and timeline *"
                                value={formData.next_steps}
                                onChange={(e) => {
                                    onFormChange('next_steps', e.target.value);
                                    if (validationErrors['next_steps']) {
                                        setValidationErrors(prev => {
                                            const newErrors = { ...prev };
                                            delete newErrors['next_steps'];
                                            return newErrors;
                                        });
                                    }
                                }}
                                disabled={isCompleted}
                                required
                                error={!!validationErrors['next_steps']}
                                helperText={validationErrors['next_steps'] || "Describe what should happen next and when"}
                            />
                        </Grid>

                        <Grid item xs={12}>
                            <Divider />
                        </Grid>

                        <Grid item xs={12}>
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={formData.crm_updates_approved}
                                        onChange={(e) => onFormChange('crm_updates_approved', e.target.checked)}
                                        disabled={isCompleted}
                                    />
                                }
                                label="Approve suggested CRM updates"
                            />

                            {draftSummary.suggested_crm_updates &&
                                Object.keys(draftSummary.suggested_crm_updates).length > 0 && (
                                    <Paper sx={{ p: 2, bgcolor: 'grey.50', mt: 1 }}>
                                        <Typography variant="subtitle2" gutterBottom>
                                            Suggested CRM Updates:
                                        </Typography>
                                        <pre style={{ fontSize: '0.875rem', margin: 0, whiteSpace: 'pre-wrap' }}>
                                            {JSON.stringify(draftSummary.suggested_crm_updates, null, 2)}
                                        </pre>
                                    </Paper>
                                )}
                        </Grid>

                        <Grid item xs={12}>
                            <TextField
                                fullWidth
                                multiline
                                rows={2}
                                label="Additional notes (optional)"
                                value={formData.additional_notes}
                                onChange={(e) => onFormChange('additional_notes', e.target.value)}
                                disabled={isCompleted}
                                helperText="Any additional context or observations"
                            />
                        </Grid>
                    </Grid>

                    {/* Action Buttons */}
                    {!isCompleted && (
                        <>
                            <Box display="flex" gap={2} mt={3}>
                                <Button
                                    variant="outlined"
                                    startIcon={<SaveIcon />}
                                    onClick={onSave}
                                    disabled={saving}
                                >
                                    Save Progress
                                </Button>
                                <Button
                                    variant="contained"
                                    onClick={() => {
                                        if (isFormValid()) {
                                            onComplete();
                                        }
                                    }}
                                    disabled={saving}
                                >
                                    Complete Validation
                                </Button>
                            </Box>

                            {Object.keys(validationErrors).length > 0 && (
                                <Alert severity="error" sx={{ mt: 2 }}>
                                    Please fix the validation errors above to complete validation.
                                </Alert>
                            )}
                        </>
                    )}

                    {isCompleted && (
                        <Alert severity="success" sx={{ mt: 2 }}>
                            Validation completed successfully.
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {/* Add Action Item Dialog */}
            <Dialog open={actionItemDialogOpen} onClose={() => setActionItemDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Add Action Item</DialogTitle>
                <DialogContent>
                    <TextField
                        fullWidth
                        label="Description *"
                        value={newActionItem.description}
                        onChange={(e) => setNewActionItem({ ...newActionItem, description: e.target.value })}
                        margin="normal"
                        required
                    />
                    <TextField
                        fullWidth
                        label="Assignee"
                        value={newActionItem.assignee}
                        onChange={(e) => setNewActionItem({ ...newActionItem, assignee: e.target.value })}
                        margin="normal"
                    />
                    <TextField
                        fullWidth
                        type="date"
                        label="Due Date"
                        value={newActionItem.due_date}
                        onChange={(e) => setNewActionItem({ ...newActionItem, due_date: e.target.value })}
                        margin="normal"
                        InputLabelProps={{ shrink: true }}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setActionItemDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={handleAddActionItem}
                        variant="contained"
                        disabled={!newActionItem.description.trim()}
                    >
                        Add
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ValidationForm;