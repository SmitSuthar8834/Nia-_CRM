"""
AI Assistant Service for Gemini API integration
"""
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.cache import cache
from .models import AISession, AIInteraction

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

logger = logging.getLogger(__name__)


class AIAssistantService:
    """
    Service class for AI assistant functionality using Google Gemini API
    """
    
    def __init__(self):
        self.model_name = settings.GEMINI_MODEL
        self.api_key = settings.GEMINI_API_KEY
        self._model = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Gemini API client"""
        if not GEMINI_AVAILABLE:
            logger.warning("Google Generative AI package not available. AI features will use fallback responses.")
            return
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured. AI features will use fallback responses.")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini AI client initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI client: {str(e)}")
            self._model = None
    
    def is_available(self) -> bool:
        """Check if AI service is available"""
        return GEMINI_AVAILABLE and self._model is not None and bool(self.api_key)
    
    def initialize_session(self, meeting_id: int, lead_context: Dict[str, Any]) -> AISession:
        """
        Initialize AI session with lead context
        
        Args:
            meeting_id: ID of the meeting
            lead_context: Dictionary containing lead information
            
        Returns:
            AISession: Created AI session instance
        """
        session_id = str(uuid.uuid4())
        
        # Create AI session
        session = AISession.objects.create(
            session_id=session_id,
            meeting_id=meeting_id,
            lead_context=lead_context,
            is_active=True
        )
        
        # Cache session for quick access
        cache_key = f"ai_session_{session_id}"
        cache.set(cache_key, {
            'session_id': session_id,
            'meeting_id': meeting_id,
            'lead_context': lead_context,
            'conversation_history': []
        }, timeout=3600)  # 1 hour
        
        logger.info(f"AI session initialized: {session_id} for meeting {meeting_id}")
        return session
    
    def analyze_conversation_context(self, conversation_context: str) -> Dict[str, Any]:
        """
        Analyze conversation context to extract key information
        
        Args:
            conversation_context: Current conversation text
            
        Returns:
            Dict containing analysis results
        """
        analysis = {
            'topics': [],
            'sentiment': 'neutral',
            'questions_asked': 0,
            'pain_points': [],
            'interests': [],
            'stage_indicators': []
        }
        
        context_lower = conversation_context.lower()
        
        # Detect topics
        business_topics = ['revenue', 'growth', 'sales', 'marketing', 'customers', 'team', 'process']
        tech_topics = ['software', 'system', 'integration', 'automation', 'data', 'analytics']
        
        for topic in business_topics + tech_topics:
            if topic in context_lower:
                analysis['topics'].append(topic)
        
        # Count questions in conversation
        analysis['questions_asked'] = context_lower.count('?')
        
        # Detect pain points
        pain_indicators = ['problem', 'issue', 'challenge', 'difficult', 'struggl', 'frustrat']
        for indicator in pain_indicators:
            if indicator in context_lower:
                # Store the base form for consistency
                base_form = indicator
                if indicator == 'struggl':
                    base_form = 'struggle'
                elif indicator == 'frustrat':
                    base_form = 'frustrating'
                analysis['pain_points'].append(base_form)
        
        # Detect interests/positive signals
        interest_indicators = ['interested', 'like', 'good', 'great', 'perfect', 'exactly']
        for indicator in interest_indicators:
            if indicator in context_lower:
                analysis['interests'].append(indicator)
        
        # Detect meeting stage indicators
        opening_indicators = ['hello', 'hi', 'nice to meet', 'introduction', 'background']
        discovery_indicators = ['tell me about', 'how do you', 'what is your', 'current process']
        closing_indicators = ['next steps', 'follow up', 'proposal', 'timeline', 'decision']
        
        if any(ind in context_lower for ind in opening_indicators):
            analysis['stage_indicators'].append('opening')
        if any(ind in context_lower for ind in discovery_indicators):
            analysis['stage_indicators'].append('discovery')
        if any(ind in context_lower for ind in closing_indicators):
            analysis['stage_indicators'].append('closing')
        
        return analysis
    
    def determine_meeting_stage(self, conversation_context: str, current_stage: str = 'general') -> str:
        """
        Determine the optimal meeting stage based on conversation analysis
        
        Args:
            conversation_context: Current conversation text
            current_stage: Current meeting stage
            
        Returns:
            str: Recommended meeting stage
        """
        analysis = self.analyze_conversation_context(conversation_context)
        stage_indicators = analysis.get('stage_indicators', [])
        
        # If we have clear stage indicators, use them with priority
        # Opening indicators take precedence if conversation is short
        context_length = len(conversation_context.split())
        
        if 'closing' in stage_indicators:
            return 'closing'
        elif 'opening' in stage_indicators and context_length < 30:
            return 'opening'
        elif 'discovery' in stage_indicators:
            return 'discovery'
        elif 'opening' in stage_indicators:
            return 'opening'
        
        # Otherwise, use heuristics based on conversation length and content
        context_length = len(conversation_context.split())
        questions_asked = analysis.get('questions_asked', 0)
        
        # Short conversation with few questions = opening
        if context_length < 50 and questions_asked < 3:
            return 'opening'
        
        # Long conversation with many topics = discovery
        elif len(analysis.get('topics', [])) > 2 and questions_asked > 5:
            return 'discovery'
        
        # Mentions of next steps, timeline, etc. = closing
        elif any(word in conversation_context.lower() for word in ['next steps', 'timeline', 'proposal', 'decision']):
            return 'closing'
        
        # Default to current stage if no clear indicators
        return current_stage
    
    def generate_meeting_suggestions(self, context: str, meeting_stage: str = 'general', 
                                   lead_context: Dict[str, Any] = None) -> List[str]:
        """
        Generate meeting suggestions based on context and lead information
        
        Args:
            context: Current conversation context
            meeting_stage: Stage of the meeting
            lead_context: Lead information for context
            
        Returns:
            List[str]: List of suggested questions/topics
        """
        try:
            # Analyze conversation context
            context_analysis = self.analyze_conversation_context(context)
            
            if self.is_available():
                suggestions = self._generate_suggestions_with_ai(
                    context, meeting_stage, lead_context or {}, context_analysis
                )
            else:
                suggestions = self._generate_fallback_suggestions(meeting_stage, context_analysis)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating meeting suggestions: {str(e)}")
            return self._generate_fallback_suggestions(meeting_stage)
    
    def _generate_suggestions_with_ai(self, context: str, meeting_stage: str, 
                                    lead_context: Dict, context_analysis: Dict) -> List[str]:
        """Generate suggestions using Gemini AI"""
        
        lead_info = self._format_lead_context(lead_context)
        topics_str = ', '.join(context_analysis.get('topics', []))
        
        prompt = f"""
        You are an AI sales assistant. Based on the conversation context and lead information, 
        suggest 3-4 relevant questions or discussion topics for a {meeting_stage} stage meeting.
        
        Lead Information:
        {lead_info}
        
        Current Conversation: {context}
        Topics Discussed: {topics_str}
        
        Provide practical, engaging suggestions that move the conversation forward.
        Return only the suggestions, one per line.
        """
        
        try:
            response = self._model.generate_content(prompt)
            suggestions = [s.strip() for s in response.text.split('\n') if s.strip()]
            return suggestions[:4]
        except Exception as e:
            logger.error(f"Gemini API error in suggestions: {str(e)}")
            raise
    
    def _generate_fallback_suggestions(self, meeting_stage: str, context_analysis: Dict = None) -> List[str]:
        """Generate fallback suggestions when AI is not available"""
        
        suggestions = {
            'opening': [
                "Tell me about your current business challenges",
                "What goals are you hoping to achieve?",
                "How did you hear about our solution?"
            ],
            'discovery': [
                "Can you walk me through your current process?",
                "What's working well in your current setup?",
                "What would an ideal solution look like?"
            ],
            'general': [
                "What questions do you have for me?",
                "How do you see this fitting into your workflow?",
                "What are your main concerns about making a change?"
            ]
        }
        
        return suggestions.get(meeting_stage, suggestions['general'])

    def generate_questions(self, session_id: str, conversation_context: str, 
                          meeting_stage: str = 'general') -> List[str]:
        """
        Generate AI-powered question suggestions
        
        Args:
            session_id: AI session ID
            conversation_context: Current conversation context
            meeting_stage: Stage of the meeting (opening, discovery, general)
            
        Returns:
            List[str]: List of suggested questions
        """
        start_time = time.time()
        
        try:
            # Get session context
            session_data = self._get_session_data(session_id)
            if not session_data:
                raise ValueError(f"Session {session_id} not found")
            
            lead_context = session_data.get('lead_context', {})
            
            # Analyze conversation context
            context_analysis = self.analyze_conversation_context(conversation_context)
            
            if self.is_available():
                questions = self._generate_questions_with_ai(
                    lead_context, conversation_context, meeting_stage, context_analysis
                )
            else:
                questions = self._generate_fallback_questions(meeting_stage, context_analysis)
            
            # Log interaction
            processing_time = time.time() - start_time
            self._log_interaction(
                session_id, 'question_suggestion',
                {
                    'conversation_context': conversation_context,
                    'meeting_stage': meeting_stage,
                    'lead_context': lead_context
                },
                {'questions': questions},
                processing_time, True
            )
            
            return questions
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error generating questions: {str(e)}")
            
            # Log failed interaction
            self._log_interaction(
                session_id, 'question_suggestion',
                {'conversation_context': conversation_context, 'meeting_stage': meeting_stage},
                {},
                processing_time, False, str(e)
            )
            
            # Return fallback questions
            return self._generate_fallback_questions(meeting_stage)
    
    def _generate_questions_with_ai(self, lead_context: Dict, conversation_context: str, 
                                   meeting_stage: str, context_analysis: Dict) -> List[str]:
        """Generate questions using Gemini AI"""
        
        # Build prompt with lead context
        lead_info = self._format_lead_context(lead_context)
        
        # Build enhanced prompt with context analysis
        topics_str = ', '.join(context_analysis.get('topics', []))
        pain_points_str = ', '.join(context_analysis.get('pain_points', []))
        interests_str = ', '.join(context_analysis.get('interests', []))
        
        prompt = f"""
        You are an AI sales assistant helping during a meeting. Based on the lead information, conversation context, and analysis, suggest 3-5 relevant questions.
        
        Lead Information:
        {lead_info}
        
        Meeting Stage: {meeting_stage}
        Conversation Context: {conversation_context}
        
        Context Analysis:
        - Topics discussed: {topics_str}
        - Pain points mentioned: {pain_points_str}
        - Positive signals: {interests_str}
        - Questions already asked: {context_analysis.get('questions_asked', 0)}
        
        Generate questions that are:
        1. Build on topics already discussed
        2. Address pain points or explore interests mentioned
        3. Appropriate for the current meeting stage
        4. Avoid repeating similar questions if many have been asked
        5. Open-ended to encourage discussion
        6. Professional and engaging
        
        Return only the questions, one per line, without numbering or bullet points.
        """
        
        try:
            response = self._model.generate_content(prompt)
            questions = [q.strip() for q in response.text.split('\n') if q.strip()]
            return questions[:5]  # Limit to 5 questions
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise
    
    def _generate_fallback_questions(self, meeting_stage: str, context_analysis: Dict = None) -> List[str]:
        """Generate fallback questions when AI is not available"""
        
        base_questions = {
            'opening': [
                "How has your business been performing this quarter?",
                "What are your main challenges right now?",
                "What goals are you hoping to achieve this year?",
                "How did you hear about our solution?",
                "Can you tell me about your role and responsibilities?"
            ],
            'discovery': [
                "Can you tell me more about your current process?",
                "What tools are you currently using?",
                "How is this impacting your team's productivity?",
                "What would an ideal solution look like for you?",
                "What's working well in your current setup?"
            ],
            'general': [
                "What would success look like for you?",
                "How do you currently handle this situation?",
                "What's your timeline for making a decision?",
                "Who else would be involved in this decision?",
                "What concerns do you have about making a change?"
            ]
        }
        
        questions = base_questions.get(meeting_stage, base_questions['general'])
        
        # Enhance questions based on context analysis if available
        if context_analysis:
            enhanced_questions = []
            
            # Add topic-specific questions
            topics = context_analysis.get('topics', [])
            if 'revenue' in topics or 'growth' in topics:
                enhanced_questions.append("How do you measure success in terms of revenue growth?")
            if 'team' in topics:
                enhanced_questions.append("How large is your team and how are they organized?")
            if 'process' in topics:
                enhanced_questions.append("What part of your process takes the most time?")
            
            # Add pain point follow-ups
            pain_points = context_analysis.get('pain_points', [])
            if pain_points:
                enhanced_questions.append("What would solving this challenge mean for your business?")
                enhanced_questions.append("How long have you been dealing with this issue?")
            
            # Add interest follow-ups
            interests = context_analysis.get('interests', [])
            if interests:
                enhanced_questions.append("What specifically interests you about this approach?")
                enhanced_questions.append("How do you see this fitting into your current workflow?")
            
            # Combine and limit questions
            all_questions = questions + enhanced_questions
            return all_questions[:5]
        
        return questions[:4]
    
    def process_meeting_transcript(self, session_id: str, transcript: str, 
                                 identify_speakers: bool = True) -> Dict[str, Any]:
        """
        Process meeting transcript with speaker identification and note extraction
        
        Args:
            session_id: AI session ID
            transcript: Raw meeting transcript
            identify_speakers: Whether to attempt speaker identification
            
        Returns:
            Dict containing processed transcript data
        """
        start_time = time.time()
        
        try:
            result = {
                'processed_transcript': transcript,
                'speakers': [],
                'structured_notes': [],
                'key_points': [],
                'decisions': [],
                'questions_raised': []
            }
            
            if identify_speakers:
                result['speakers'] = self._identify_speakers(transcript)
                result['structured_notes'] = self._structure_notes_by_speaker(transcript, result['speakers'])
            else:
                result['structured_notes'] = self._structure_notes_simple(transcript)
            
            # Extract key information
            result['key_points'] = self._extract_key_points(transcript)
            result['decisions'] = self._extract_decisions(transcript)
            result['questions_raised'] = self._extract_questions_from_transcript(transcript)
            
            # Log interaction
            processing_time = time.time() - start_time
            self._log_interaction(
                session_id, 'note_processing',
                {'transcript_length': len(transcript), 'identify_speakers': identify_speakers},
                result,
                processing_time, True
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing transcript: {str(e)}")
            
            # Log failed interaction
            self._log_interaction(
                session_id, 'note_processing',
                {'transcript_length': len(transcript)},
                {},
                processing_time, False, str(e)
            )
            
            # Return basic processing
            return {
                'processed_transcript': transcript,
                'speakers': [],
                'structured_notes': [{'speaker': 'Unknown', 'content': transcript}],
                'key_points': [],
                'decisions': [],
                'questions_raised': []
            }
    
    def _identify_speakers(self, transcript: str) -> List[Dict[str, str]]:
        """
        Identify speakers in the transcript using simple heuristics
        
        Args:
            transcript: Meeting transcript
            
        Returns:
            List of identified speakers
        """
        speakers = []
        lines = transcript.split('\n')
        
        # Look for common speaker patterns
        speaker_patterns = [
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):',  # "John Smith:"
            r'^([A-Z]+):',  # "JOHN:"
            r'^\[([^\]]+)\]:',  # "[John Smith]:"
            r'^(\w+)\s*-',  # "John -"
        ]
        
        import re
        identified_speakers = set()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            for pattern in speaker_patterns:
                match = re.match(pattern, line)
                if match:
                    speaker_name = match.group(1).strip()
                    if len(speaker_name) > 1 and len(speaker_name) < 50:
                        identified_speakers.add(speaker_name)
        
        # Convert to list of dicts
        for i, speaker in enumerate(sorted(identified_speakers)):
            speakers.append({
                'id': f'speaker_{i+1}',
                'name': speaker,
                'role': 'participant'
            })
        
        # Add default speakers if none found
        if not speakers:
            speakers = [
                {'id': 'speaker_1', 'name': 'Host', 'role': 'host'},
                {'id': 'speaker_2', 'name': 'Participant', 'role': 'participant'}
            ]
        
        return speakers
    
    def _structure_notes_by_speaker(self, transcript: str, speakers: List[Dict]) -> List[Dict]:
        """
        Structure notes by identified speakers
        
        Args:
            transcript: Meeting transcript
            speakers: List of identified speakers
            
        Returns:
            List of structured notes by speaker
        """
        structured_notes = []
        lines = transcript.split('\n')
        current_speaker = 'Unknown'
        current_content = []
        
        import re
        speaker_names = {speaker['name']: speaker['id'] for speaker in speakers}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with a speaker identifier
            speaker_found = False
            for pattern in [r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):(.*)$', 
                           r'^([A-Z]+):(.*)$', 
                           r'^\[([^\]]+)\]:(.*)$']:
                match = re.match(pattern, line)
                if match:
                    # Save previous speaker's content
                    if current_content:
                        structured_notes.append({
                            'speaker': current_speaker,
                            'speaker_id': speaker_names.get(current_speaker, 'unknown'),
                            'content': ' '.join(current_content).strip(),
                            'timestamp': None
                        })
                        current_content = []
                    
                    # Start new speaker section
                    current_speaker = match.group(1).strip()
                    content = match.group(2).strip() if len(match.groups()) > 1 else ''
                    if content:
                        current_content.append(content)
                    speaker_found = True
                    break
            
            if not speaker_found:
                current_content.append(line)
        
        # Add final speaker's content
        if current_content:
            structured_notes.append({
                'speaker': current_speaker,
                'speaker_id': speaker_names.get(current_speaker, 'unknown'),
                'content': ' '.join(current_content).strip(),
                'timestamp': None
            })
        
        return structured_notes
    
    def _structure_notes_simple(self, transcript: str) -> List[Dict]:
        """
        Structure notes without speaker identification
        
        Args:
            transcript: Meeting transcript
            
        Returns:
            List of structured notes
        """
        # Split transcript into logical sections
        sections = []
        paragraphs = transcript.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                sections.append({
                    'speaker': f'Section {i+1}',
                    'speaker_id': f'section_{i+1}',
                    'content': paragraph.strip(),
                    'timestamp': None
                })
        
        return sections if sections else [{
            'speaker': 'Meeting',
            'speaker_id': 'meeting',
            'content': transcript,
            'timestamp': None
        }]
    
    def _extract_key_points(self, transcript: str) -> List[str]:
        """
        Extract key points from transcript using keyword analysis
        
        Args:
            transcript: Meeting transcript
            
        Returns:
            List of key points
        """
        key_points = []
        lines = transcript.split('\n')
        
        # Keywords that indicate important points
        importance_indicators = [
            'important', 'key', 'critical', 'essential', 'main point',
            'priority', 'focus', 'goal', 'objective', 'requirement'
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            if any(indicator in line_lower for indicator in importance_indicators):
                if len(line.strip()) > 10:  # Avoid very short lines
                    key_points.append(line.strip())
        
        return key_points[:10]  # Limit to top 10 key points
    
    def _extract_decisions(self, transcript: str) -> List[str]:
        """
        Extract decisions made during the meeting
        
        Args:
            transcript: Meeting transcript
            
        Returns:
            List of decisions
        """
        decisions = []
        lines = transcript.split('\n')
        
        # Keywords that indicate decisions
        decision_indicators = [
            'decided', 'agreed', 'concluded', 'determined', 'resolved',
            'we will', 'let\'s', 'going to', 'plan to', 'commit to'
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            if any(indicator in line_lower for indicator in decision_indicators):
                if len(line.strip()) > 15:  # Avoid very short lines
                    decisions.append(line.strip())
        
        return decisions[:8]  # Limit to top 8 decisions
    
    def _extract_questions_from_transcript(self, transcript: str) -> List[str]:
        """
        Extract questions raised during the meeting
        
        Args:
            transcript: Meeting transcript
            
        Returns:
            List of questions
        """
        questions = []
        lines = transcript.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.endswith('?') and len(line) > 10:
                questions.append(line)
        
        return questions[:15]  # Limit to top 15 questions
    
    def extract_action_items(self, session_id: str, meeting_notes: str) -> List[Dict[str, Any]]:
        """
        Extract action items from meeting notes
        
        Args:
            session_id: AI session ID
            meeting_notes: Meeting notes text
            
        Returns:
            List[Dict]: List of extracted action items
        """
        start_time = time.time()
        
        try:
            if self.is_available():
                action_items = self._extract_action_items_with_ai(meeting_notes)
            else:
                action_items = self._extract_fallback_action_items(meeting_notes)
            
            # Log interaction
            processing_time = time.time() - start_time
            self._log_interaction(
                session_id, 'action_extraction',
                {'meeting_notes': meeting_notes},
                {'action_items': action_items},
                processing_time, True
            )
            
            return action_items
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error extracting action items: {str(e)}")
            
            # Log failed interaction
            self._log_interaction(
                session_id, 'action_extraction',
                {'meeting_notes': meeting_notes},
                {},
                processing_time, False, str(e)
            )
            
            # Return fallback action items
            return self._extract_fallback_action_items(meeting_notes)
    
    def extract_action_items_from_transcript(self, session_id: str, transcript: str, 
                                           structured_notes: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Extract action items from meeting transcript with speaker attribution
        
        Args:
            session_id: AI session ID
            transcript: Meeting transcript
            structured_notes: Pre-processed structured notes
            
        Returns:
            List of action items with speaker attribution
        """
        start_time = time.time()
        
        try:
            if self.is_available():
                action_items = self._extract_action_items_with_ai_enhanced(transcript, structured_notes)
            else:
                action_items = self._extract_action_items_fallback_enhanced(transcript, structured_notes)
            
            # Log interaction
            processing_time = time.time() - start_time
            self._log_interaction(
                session_id, 'action_extraction',
                {'transcript_length': len(transcript), 'has_structured_notes': bool(structured_notes)},
                {'action_items': action_items},
                processing_time, True
            )
            
            return action_items
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error extracting action items from transcript: {str(e)}")
            
            # Log failed interaction
            self._log_interaction(
                session_id, 'action_extraction',
                {'transcript_length': len(transcript)},
                {},
                processing_time, False, str(e)
            )
            
            # Return fallback action items
            return self._extract_action_items_fallback_enhanced(transcript, structured_notes)
    
    def _extract_action_items_with_ai_enhanced(self, transcript: str, 
                                             structured_notes: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Extract action items using Gemini AI with enhanced context
        
        Args:
            transcript: Meeting transcript
            structured_notes: Structured notes by speaker
            
        Returns:
            List of enhanced action items
        """
        
        # Build enhanced prompt with speaker context
        context = f"Meeting Transcript:\n{transcript}\n\n"
        
        if structured_notes:
            context += "Speaker Breakdown:\n"
            for note in structured_notes:
                context += f"{note['speaker']}: {note['content'][:200]}...\n"
        
        prompt = f"""
        Analyze the following meeting content and extract action items. For each action item, identify:
        1. Description of the task
        2. Who is responsible (assignee) - use actual names from the transcript when possible
        3. Due date if mentioned, otherwise suggest a reasonable timeframe
        4. Priority level (high, medium, low)
        5. Which speaker mentioned or agreed to the action
        
        {context}
        
        Return the action items in JSON format as a list of objects with keys: 
        description, assignee, due_date, priority, mentioned_by, context.
        If no action items are found, return an empty list.
        Only return valid JSON, no additional text.
        """
        
        try:
            response = self._model.generate_content(prompt)
            # Parse JSON response
            import json
            action_items = json.loads(response.text)
            return action_items if isinstance(action_items, list) else []
        except Exception as e:
            logger.error(f"Error parsing AI action items response: {str(e)}")
            return []
    
    def _extract_action_items_fallback_enhanced(self, transcript: str, 
                                              structured_notes: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Extract action items using enhanced keyword matching
        
        Args:
            transcript: Meeting transcript
            structured_notes: Structured notes by speaker
            
        Returns:
            List of enhanced action items
        """
        
        action_items = []
        
        # Enhanced action keywords
        action_keywords = [
            'follow up', 'send', 'provide', 'schedule', 'call', 'email',
            'prepare', 'review', 'complete', 'deliver', 'submit', 'create',
            'update', 'check', 'confirm', 'arrange', 'organize', 'contact'
        ]
        
        # Process structured notes if available
        if structured_notes:
            for note in structured_notes:
                content = note['content'].lower()
                speaker = note['speaker']
                
                for keyword in action_keywords:
                    if keyword in content:
                        # Find sentences containing the keyword
                        sentences = note['content'].split('.')
                        for sentence in sentences:
                            if keyword in sentence.lower() and len(sentence.strip()) > 10:
                                action_items.append({
                                    'description': sentence.strip(),
                                    'assignee': speaker,
                                    'due_date': None,
                                    'priority': 'medium',
                                    'mentioned_by': speaker,
                                    'context': note['content'][:100] + '...'
                                })
        else:
            # Fallback to simple line processing
            lines = transcript.split('\n')
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in action_keywords):
                    action_items.append({
                        'description': line.strip(),
                        'assignee': 'To be assigned',
                        'due_date': None,
                        'priority': 'medium',
                        'mentioned_by': 'Unknown',
                        'context': line.strip()
                    })
        
        return action_items[:10]  # Limit to 10 items
    
    def _extract_action_items_with_ai(self, meeting_notes: str) -> List[Dict[str, Any]]:
        """Extract action items using Gemini AI"""
        
        prompt = f"""
        Analyze the following meeting notes and extract action items. For each action item, identify:
        1. Description of the task
        2. Who is responsible (assignee)
        3. Due date if mentioned, otherwise suggest a reasonable timeframe
        
        Meeting Notes:
        {meeting_notes}
        
        Return the action items in JSON format as a list of objects with keys: description, assignee, due_date.
        If no action items are found, return an empty list.
        Only return valid JSON, no additional text.
        """
        
        try:
            response = self._model.generate_content(prompt)
            # Parse JSON response
            import json
            action_items = json.loads(response.text)
            return action_items if isinstance(action_items, list) else []
        except Exception as e:
            logger.error(f"Error parsing AI action items response: {str(e)}")
            return []
    
    def _extract_fallback_action_items(self, meeting_notes: str) -> List[Dict[str, Any]]:
        """Extract action items using simple keyword matching"""
        
        action_keywords = [
            'follow up', 'send', 'provide', 'schedule', 'call', 'email',
            'prepare', 'review', 'complete', 'deliver', 'submit'
        ]
        
        action_items = []
        lines = meeting_notes.lower().split('\n')
        
        for line in lines:
            if any(keyword in line for keyword in action_keywords):
                action_items.append({
                    'description': line.strip().capitalize(),
                    'assignee': 'To be assigned',
                    'due_date': None
                })
        
        return action_items[:5]  # Limit to 5 items
    
    def generate_summary(self, session_id: str, meeting_transcript: str, 
                        meeting_notes: str = '') -> str:
        """
        Generate meeting summary
        
        Args:
            session_id: AI session ID
            meeting_transcript: Full meeting transcript
            meeting_notes: Additional meeting notes
            
        Returns:
            str: Generated meeting summary
        """
        start_time = time.time()
        
        try:
            if self.is_available():
                summary = self._generate_summary_with_ai(meeting_transcript, meeting_notes)
            else:
                summary = self._generate_fallback_summary(meeting_transcript, meeting_notes)
            
            # Log interaction
            processing_time = time.time() - start_time
            self._log_interaction(
                session_id, 'summary_generation',
                {'meeting_transcript': meeting_transcript, 'meeting_notes': meeting_notes},
                {'summary': summary},
                processing_time, True
            )
            
            return summary
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error generating summary: {str(e)}")
            
            # Log failed interaction
            self._log_interaction(
                session_id, 'summary_generation',
                {'meeting_transcript': meeting_transcript, 'meeting_notes': meeting_notes},
                {},
                processing_time, False, str(e)
            )
            
            # Return fallback summary
            return self._generate_fallback_summary(meeting_transcript, meeting_notes)
    
    def _generate_summary_with_ai(self, meeting_transcript: str, meeting_notes: str) -> str:
        """Generate summary using Gemini AI"""
        
        content = f"Meeting Transcript:\n{meeting_transcript}\n\nAdditional Notes:\n{meeting_notes}"
        
        prompt = f"""
        Create a concise meeting summary based on the following content. Include:
        1. Key discussion points
        2. Decisions made
        3. Next steps
        4. Important outcomes
        
        Content:
        {content}
        
        Keep the summary professional, clear, and under 300 words.
        """
        
        try:
            response = self._model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error in summary generation: {str(e)}")
            raise
    
    def _generate_fallback_summary(self, meeting_transcript: str, meeting_notes: str) -> str:
        """Generate fallback summary when AI is not available"""
        
        content_length = len(meeting_transcript) + len(meeting_notes)
        
        return f"""
        Meeting Summary:
        - Meeting conducted with discussion on key business topics
        - Various points were covered during the conversation
        - Next steps and follow-up actions were identified
        - Content processed: {content_length} characters
        
        Note: This is a basic summary. AI-powered detailed summaries are currently unavailable.
        """
    
    def _get_session_data(self, session_id: str) -> Optional[Dict]:
        """Get session data from cache or database"""
        
        # Try cache first
        cache_key = f"ai_session_{session_id}"
        session_data = cache.get(cache_key)
        
        if session_data:
            return session_data
        
        # Fallback to database
        try:
            session = AISession.objects.get(session_id=session_id, is_active=True)
            session_data = {
                'session_id': session.session_id,
                'meeting_id': session.meeting_id,
                'lead_context': session.lead_context,
                'conversation_history': session.conversation_history
            }
            
            # Cache for future use
            cache.set(cache_key, session_data, timeout=3600)
            return session_data
            
        except AISession.DoesNotExist:
            return None
    
    def _format_lead_context(self, lead_context: Dict) -> str:
        """Format lead context for AI prompts"""
        
        if not lead_context:
            return "No lead information available"
        
        formatted = []
        
        if 'name' in lead_context:
            formatted.append(f"Contact: {lead_context['name']}")
        if 'company' in lead_context:
            formatted.append(f"Company: {lead_context['company']}")
        if 'email' in lead_context:
            formatted.append(f"Email: {lead_context['email']}")
        if 'status' in lead_context:
            formatted.append(f"Lead Status: {lead_context['status']}")
        if 'source' in lead_context:
            formatted.append(f"Lead Source: {lead_context['source']}")
        
        return '\n'.join(formatted) if formatted else "Limited lead information available"
    
    def _log_interaction(self, session_id: str, interaction_type: str, 
                        input_data: Dict, output_data: Dict, 
                        processing_time: float, success: bool, 
                        error_message: str = ''):
        """Log AI interaction to database"""
        
        try:
            session = AISession.objects.get(session_id=session_id)
            AIInteraction.objects.create(
                session=session,
                interaction_type=interaction_type,
                input_data=input_data,
                output_data=output_data,
                processing_time=processing_time,
                success=success,
                error_message=error_message
            )
        except AISession.DoesNotExist:
            logger.error(f"Session {session_id} not found for interaction logging")
        except Exception as e:
            logger.error(f"Failed to log AI interaction: {str(e)}")
    
    def end_session(self, session_id: str):
        """End AI session and cleanup"""
        
        try:
            session = AISession.objects.get(session_id=session_id)
            session.is_active = False
            session.save()
            
            # Remove from cache
            cache_key = f"ai_session_{session_id}"
            cache.delete(cache_key)
            
            logger.info(f"AI session ended: {session_id}")
            
        except AISession.DoesNotExist:
            logger.warning(f"Session {session_id} not found for ending")