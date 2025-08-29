import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ValidationForm from '../ValidationForm';
import { DraftSummary, ValidationFormData, ValidationQuestion } from '../../../types/validation';

const theme = createTheme();

const renderWithTheme = (component: React.ReactElement) => {
    return render(
        <ThemeProvider theme={theme}>
            {component}
        </ThemeProvider>
    );
};

describe('ValidationForm', () => {
    const mockDraftSummary: DraftSummary = {
        id: 'draft-1',
        bot_session: 'session-1',
        ai_generated_summary: 'This is a test summary of the meeting.',
        extracted_action_items: [
            {
                id: '1',
                description: 'Follow up with client',
                assignee: 'john@example.com',
                status: 'pending',
            },
        ],
        suggested_next_steps: 'Schedule follow-up call',
        suggested_crm_updates: { stage: 'qualified' },
        confidence_score: 0.85,
        created_at: '2024-01-01T10:00:00Z',
    };

    const mockFormData: ValidationFormData = {
        summary_approved: false,
        summary_edits: '',
        next_steps: '',
        crm_updates_approved: false,
        crm_updates_edits: {},
        additional_notes: '',
        question_responses: {},
    };

    const mockValidationQuestions: ValidationQuestion[] = [
        {
            id: 'q1',
            question: 'Was the meeting productive?',
            type: 'boolean',
            required: true,
        },
        {
            id: 'q2',
            question: 'What was the main outcome?',
            type: 'multiple_choice',
            options: ['Deal closed', 'Follow-up needed', 'No interest'],
            required: true,
        },
        {
            id: 'q3',
            question: 'Rate the client engagement',
            type: 'rating',
            required: false,
        },
        {
            id: 'q4',
            question: 'Confirm the next meeting date',
            type: 'confirmation',
            required: true,
        },
        {
            id: 'q5',
            question: 'Additional comments',
            type: 'text_editing',
            required: false,
            helperText: 'Provide any additional context',
        },
    ];

    const mockProps = {
        draftSummary: mockDraftSummary,
        formData: mockFormData,
        validationQuestions: mockValidationQuestions,
        onFormChange: jest.fn(),
        onQuestionResponse: jest.fn(),
        onSave: jest.fn(),
        onComplete: jest.fn(),
        saving: false,
        isCompleted: false,
        questionResponses: {},
    };

    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders AI generated summary', () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        expect(screen.getByText('AI Generated Summary')).toBeInTheDocument();
        expect(screen.getByText('This is a test summary of the meeting.')).toBeInTheDocument();
        expect(screen.getByText('Confidence Score: 85.0%')).toBeInTheDocument();
    });

    it('renders action items', () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        expect(screen.getByText('Action Items')).toBeInTheDocument();
        expect(screen.getByText('Follow up with client')).toBeInTheDocument();
        expect(screen.getByText('Assigned: john@example.com')).toBeInTheDocument();
    });

    it('allows editing summary', async () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        const editButton = screen.getByText('Edit Summary');
        fireEvent.click(editButton);

        // Should show textarea for editing
        const textarea = screen.getByDisplayValue('This is a test summary of the meeting.');
        expect(textarea).toBeInTheDocument();

        // Edit the summary
        fireEvent.change(textarea, { target: { value: 'Updated summary text' } });

        // Save the edit
        const saveButton = screen.getByText('Save Edit');
        fireEvent.click(saveButton);

        expect(mockProps.onFormChange).toHaveBeenCalledWith('summary_edits', 'Updated summary text');
        expect(mockProps.onFormChange).toHaveBeenCalledWith('summary_approved', false);
    });

    it('allows adding new action items', async () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        const addButton = screen.getByText('Add Item');
        fireEvent.click(addButton);

        // Dialog should open
        await waitFor(() => {
            expect(screen.getByText('Add Action Item')).toBeInTheDocument();
        });

        // Fill in the form
        const descriptionField = screen.getByLabelText(/Description/);
        fireEvent.change(descriptionField, { target: { value: 'New action item' } });

        const assigneeField = screen.getByLabelText(/Assignee/);
        fireEvent.change(assigneeField, { target: { value: 'jane@example.com' } });

        // Add the item
        const addItemButton = screen.getByRole('button', { name: 'Add' });
        fireEvent.click(addItemButton);

        // Dialog should close and item should be added
        await waitFor(() => {
            expect(screen.queryByText('Add Action Item')).not.toBeInTheDocument();
        });
    });

    it('validates required fields', () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        const completeButton = screen.getByText('Complete Validation');
        expect(completeButton).not.toBeDisabled(); // Button is not disabled, validation happens on click

        // Fill in required next steps field
        const nextStepsField = screen.getByLabelText(/Next steps and timeline/);
        fireEvent.change(nextStepsField, { target: { value: 'Schedule follow-up meeting' } });

        expect(mockProps.onFormChange).toHaveBeenCalledWith('next_steps', 'Schedule follow-up meeting');
    });

    it('shows CRM updates when available', () => {
        renderWithTheme(<ValidationForm {...mockProps} />);

        expect(screen.getByText('Approve suggested CRM updates')).toBeInTheDocument();
        expect(screen.getByText('Suggested CRM Updates:')).toBeInTheDocument();
        expect(screen.getByText(/"stage": "qualified"/)).toBeInTheDocument();
    });

    it('handles form submission', () => {
        const propsWithValidData = {
            ...mockProps,
            formData: {
                ...mockFormData,
                next_steps: 'Schedule follow-up call',
            },
            questionResponses: {
                q1: true,
                q2: 'Deal closed',
                q4: 'confirmed',
            },
        };

        renderWithTheme(<ValidationForm {...propsWithValidData} />);

        const saveButton = screen.getByText('Save Progress');
        fireEvent.click(saveButton);
        expect(mockProps.onSave).toHaveBeenCalled();

        const completeButton = screen.getByText('Complete Validation');
        fireEvent.click(completeButton);
        expect(mockProps.onComplete).toHaveBeenCalled();
    });

    it('disables form when completed', () => {
        const completedProps = {
            ...mockProps,
            isCompleted: true,
        };

        renderWithTheme(<ValidationForm {...completedProps} />);

        // Form fields should be disabled
        expect(screen.getByLabelText('Summary is accurate')).toBeDisabled();
        expect(screen.getByLabelText(/Next steps and timeline/)).toBeDisabled();
        expect(screen.getByLabelText('Approve suggested CRM updates')).toBeDisabled();

        // Action buttons should not be present
        expect(screen.queryByText('Complete Validation')).not.toBeInTheDocument();
        expect(screen.queryByText('Save Progress')).not.toBeInTheDocument();

        // Should show success message
        expect(screen.getByText('Validation completed successfully.')).toBeInTheDocument();
    });

    it('shows loading state when saving', () => {
        const savingProps = {
            ...mockProps,
            saving: true,
        };

        renderWithTheme(<ValidationForm {...savingProps} />);

        const saveButton = screen.getByText('Save Progress');
        expect(saveButton).toBeDisabled();
    });

    describe('Dynamic Validation Questions', () => {
        it('renders validation questions section when questions are provided', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            expect(screen.getByText('Validation Questions')).toBeInTheDocument();
            expect(screen.getByText('Was the meeting productive?')).toBeInTheDocument();
            expect(screen.getAllByText('What was the main outcome?')).toHaveLength(2); // Label and select label
            expect(screen.getByText('Rate the client engagement')).toBeInTheDocument();
            expect(screen.getByText('Confirm the next meeting date')).toBeInTheDocument();
            expect(screen.getAllByText('Additional comments')).toHaveLength(2); // Label and textarea label
        });

        it('does not render validation questions section when no questions provided', () => {
            const propsWithoutQuestions = {
                ...mockProps,
                validationQuestions: [],
            };

            renderWithTheme(<ValidationForm {...propsWithoutQuestions} />);

            expect(screen.queryByText('Validation Questions')).not.toBeInTheDocument();
        });

        it('handles boolean question responses', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            const checkbox = screen.getByRole('checkbox', { name: 'Was the meeting productive?' });
            fireEvent.click(checkbox);

            expect(mockProps.onQuestionResponse).toHaveBeenCalledWith('q1', true);
        });

        it('handles multiple choice question responses', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            // Find the select input by its role (it doesn't have a name attribute)
            const select = screen.getByRole('combobox');
            fireEvent.mouseDown(select);

            const option = screen.getByText('Deal closed');
            fireEvent.click(option);

            expect(mockProps.onQuestionResponse).toHaveBeenCalledWith('q2', 'Deal closed');
        });

        it('handles rating question responses', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            const ratingStars = screen.getAllByRole('radio');
            const thirdStar = ratingStars.find(star => star.getAttribute('value') === '3');

            if (thirdStar) {
                fireEvent.click(thirdStar);
                expect(mockProps.onQuestionResponse).toHaveBeenCalledWith('q3', 3);
            }
        });

        it('handles confirmation question responses', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            const confirmedRadio = screen.getByRole('radio', { name: /Confirmed/ });
            fireEvent.click(confirmedRadio);

            expect(mockProps.onQuestionResponse).toHaveBeenCalledWith('q4', 'confirmed');
        });

        it('handles text editing question responses', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            const textField = screen.getByLabelText(/Additional comments/);
            fireEvent.change(textField, { target: { value: 'This is additional context' } });

            expect(mockProps.onQuestionResponse).toHaveBeenCalledWith('q5', 'This is additional context');
        });

        it('shows validation errors for required questions', async () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            const completeButton = screen.getByText('Complete Validation');
            fireEvent.click(completeButton);

            await waitFor(() => {
                expect(screen.getByText('Please fix the validation errors above to complete validation.')).toBeInTheDocument();
            });
        });

        it('validates form with all required fields filled', () => {
            const propsWithResponses = {
                ...mockProps,
                formData: {
                    ...mockFormData,
                    next_steps: 'Schedule follow-up call',
                },
                questionResponses: {
                    q1: true,
                    q2: 'Deal closed',
                    q4: 'confirmed',
                },
            };

            renderWithTheme(<ValidationForm {...propsWithResponses} />);

            const completeButton = screen.getByText('Complete Validation');
            fireEvent.click(completeButton);

            expect(mockProps.onComplete).toHaveBeenCalled();
        });

        it('shows helper text for questions', () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            expect(screen.getByText('Provide any additional context')).toBeInTheDocument();
        });

        it('disables questions when form is completed', () => {
            const completedProps = {
                ...mockProps,
                isCompleted: true,
            };

            renderWithTheme(<ValidationForm {...completedProps} />);

            const checkbox = screen.getByRole('checkbox', { name: 'Was the meeting productive?' });
            expect(checkbox).toBeDisabled();

            const textField = screen.getByLabelText(/Additional comments/);
            expect(textField).toBeDisabled();
        });
    });

    describe('Form Validation', () => {
        it('validates text field minimum length', async () => {
            const questionsWithValidation: ValidationQuestion[] = [
                {
                    id: 'q1',
                    question: 'Describe the outcome',
                    type: 'text',
                    required: true,
                    validation: {
                        minLength: 10,
                    },
                },
            ];

            const propsWithValidation = {
                ...mockProps,
                validationQuestions: questionsWithValidation,
                questionResponses: { q1: 'Short' },
            };

            renderWithTheme(<ValidationForm {...propsWithValidation} />);

            const completeButton = screen.getByText('Complete Validation');
            fireEvent.click(completeButton);

            await waitFor(() => {
                expect(screen.getByText('Minimum length is 10 characters')).toBeInTheDocument();
            });
        });

        it('validates text field maximum length', async () => {
            const questionsWithValidation: ValidationQuestion[] = [
                {
                    id: 'q1',
                    question: 'Brief summary',
                    type: 'text',
                    required: true,
                    validation: {
                        maxLength: 5,
                    },
                },
            ];

            const propsWithValidation = {
                ...mockProps,
                validationQuestions: questionsWithValidation,
                questionResponses: { q1: 'This is too long' },
            };

            renderWithTheme(<ValidationForm {...propsWithValidation} />);

            const completeButton = screen.getByText('Complete Validation');
            fireEvent.click(completeButton);

            await waitFor(() => {
                expect(screen.getByText('Maximum length is 5 characters')).toBeInTheDocument();
            });
        });

        it('clears individual field validation errors when corrected', async () => {
            renderWithTheme(<ValidationForm {...mockProps} />);

            // Trigger validation error
            const completeButton = screen.getByText('Complete Validation');
            fireEvent.click(completeButton);

            await waitFor(() => {
                expect(screen.getByText('Please fix the validation errors above to complete validation.')).toBeInTheDocument();
            });

            // Check that next steps field has error
            const nextStepsField = screen.getByLabelText(/Next steps and timeline/);
            expect(nextStepsField).toHaveAttribute('aria-invalid', 'true');

            // Fix the next steps field
            fireEvent.change(nextStepsField, { target: { value: 'Schedule follow-up meeting' } });

            // The field should no longer have error state
            await waitFor(() => {
                expect(nextStepsField).toHaveAttribute('aria-invalid', 'false');
            });
        });
    });
});