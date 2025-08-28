"""
Real-time transcription service for audio stream processing
Handles live transcription, speaker identification, and transcript chunking
Enhanced with AI-powered summary generation and action item extraction
"""
import asyncio
import logging
import time
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from collections import deque
import hashlib
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AudioQuality(Enum):
    """Audio quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


class SpeakerRole(Enum):
    """Speaker role types"""
    HOST = "host"
    PARTICIPANT = "participant"
    UNKNOWN = "unknown"


@dataclass
class AudioChunk:
    """Audio data chunk for processing"""
    chunk_id: str
    audio_data: bytes
    timestamp: float
    duration: float
    sample_rate: int = 16000
    channels: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'chunk_id': self.chunk_id,
            'timestamp': self.timestamp,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'data_size': len(self.audio_data)
        }


@dataclass
class Speaker:
    """Speaker identification data"""
    speaker_id: str
    name: Optional[str] = None
    role: SpeakerRole = SpeakerRole.UNKNOWN
    confidence: float = 0.0
    voice_signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'speaker_id': self.speaker_id,
            'name': self.name,
            'role': self.role.value,
            'confidence': self.confidence,
            'voice_signature': self.voice_signature
        }


@dataclass
class TranscriptChunk:
    """Individual transcript chunk with metadata"""
    chunk_id: str
    text: str
    speaker: Speaker
    start_time: float
    end_time: float
    confidence: float
    is_final: bool = False
    language: str = "en-US"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'speaker': self.speaker.to_dict(),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'confidence': self.confidence,
            'is_final': self.is_final,
            'language': self.language
        }


@dataclass
class ActionItem:
    """Action item extracted from meeting transcript"""
    description: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "medium"  # low, medium, high
    confidence: float = 0.0
    source_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'description': self.description,
            'assignee': self.assignee,
            'due_date': self.due_date,
            'priority': self.priority,
            'confidence': self.confidence,
            'source_text': self.source_text
        }


@dataclass
class MeetingSummary:
    """AI-generated meeting summary"""
    summary_text: str
    key_points: List[str]
    action_items: List[ActionItem]
    next_steps: List[str]
    decisions_made: List[str]
    confidence_score: float
    generated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'summary_text': self.summary_text,
            'key_points': self.key_points,
            'action_items': [item.to_dict() for item in self.action_items],
            'next_steps': self.next_steps,
            'decisions_made': self.decisions_made,
            'confidence_score': self.confidence_score,
            'generated_at': self.generated_at
        }


@dataclass
class TranscriptionSession:
    """Transcription session state"""
    session_id: str
    stream_id: str
    is_active: bool = True
    audio_quality: AudioQuality = AudioQuality.GOOD
    speakers: Dict[str, Speaker] = field(default_factory=dict)
    transcript_chunks: List[TranscriptChunk] = field(default_factory=list)
    error_count: int = 0
    start_time: float = field(default_factory=time.time)
    draft_summary: Optional[MeetingSummary] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'stream_id': self.stream_id,
            'is_active': self.is_active,
            'audio_quality': self.audio_quality.value,
            'speakers': {k: v.to_dict() for k, v in self.speakers.items()},
            'transcript_chunks': [chunk.to_dict() for chunk in self.transcript_chunks],
            'error_count': self.error_count,
            'start_time': self.start_time,
            'chunk_count': len(self.transcript_chunks),
            'draft_summary': self.draft_summary.to_dict() if self.draft_summary else None
        }


class BaseTranscriptionEngine(ABC):
    """Abstract base class for transcription engines"""
    
    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.logger = logging.getLogger(f"{__name__}.{engine_name}")
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the transcription engine"""
        pass
    
    @abstractmethod
    async def transcribe_chunk(self, audio_chunk: AudioChunk) -> TranscriptChunk:
        """Transcribe a single audio chunk"""
        pass
    
    @abstractmethod
    async def identify_speaker(self, audio_chunk: AudioChunk) -> Speaker:
        """Identify speaker from audio chunk"""
        pass
    
    @abstractmethod
    async def generate_summary(self, transcript: str, speakers: Dict[str, Speaker]) -> MeetingSummary:
        """Generate AI-powered meeting summary from transcript"""
        pass
    
    @abstractmethod
    async def extract_action_items(self, transcript: str) -> List[ActionItem]:
        """Extract action items from transcript"""
        pass
    
    @abstractmethod
    async def suggest_next_steps(self, transcript: str, summary: str) -> List[str]:
        """Suggest next steps based on meeting content"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass


class MockTranscriptionEngine(BaseTranscriptionEngine):
    """Mock transcription engine for testing and development"""
    
    def __init__(self):
        super().__init__("mock")
        self.speakers_db = {}
        self.chunk_counter = 0
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize mock engine"""
        self.logger.info("Initializing mock transcription engine")
        await asyncio.sleep(0.1)  # Simulate initialization time
        return True
    
    async def transcribe_chunk(self, audio_chunk: AudioChunk) -> TranscriptChunk:
        """Mock transcription of audio chunk"""
        self.chunk_counter += 1
        
        # Simulate processing time
        await asyncio.sleep(0.05)
        
        # Generate mock transcript based on chunk properties
        mock_texts = [
            "Hello everyone, welcome to today's meeting.",
            "Thank you for joining us today.",
            "Let's start with the agenda items.",
            "I'd like to discuss the project timeline.",
            "What are your thoughts on this approach?",
            "That sounds like a great idea.",
            "Let me share my screen to show the data.",
            "Can everyone see the presentation?",
            "I think we should move forward with this plan.",
            "Any questions before we wrap up?"
        ]
        
        text = mock_texts[self.chunk_counter % len(mock_texts)]
        
        # Create mock speaker
        speaker = await self.identify_speaker(audio_chunk)
        
        chunk = TranscriptChunk(
            chunk_id=f"chunk_{self.chunk_counter}",
            text=text,
            speaker=speaker,
            start_time=audio_chunk.timestamp,
            end_time=audio_chunk.timestamp + audio_chunk.duration,
            confidence=0.85 + (hash(text) % 15) / 100,  # Mock confidence 0.85-1.0
            is_final=True,
            language="en-US"
        )
        
        self.logger.debug(f"Transcribed chunk: {text[:50]}...")
        return chunk
    
    async def identify_speaker(self, audio_chunk: AudioChunk) -> Speaker:
        """Mock speaker identification"""
        # Generate consistent speaker ID based on audio properties
        speaker_hash = hashlib.md5(
            f"{audio_chunk.sample_rate}_{audio_chunk.channels}_{len(audio_chunk.audio_data) % 3}".encode()
        ).hexdigest()[:8]
        
        speaker_id = f"speaker_{speaker_hash}"
        
        if speaker_id not in self.speakers_db:
            # Create new speaker
            speaker_names = ["Alice Johnson", "Bob Smith", "Carol Davis", "David Wilson"]
            name = speaker_names[len(self.speakers_db) % len(speaker_names)]
            
            role = SpeakerRole.HOST if len(self.speakers_db) == 0 else SpeakerRole.PARTICIPANT
            
            self.speakers_db[speaker_id] = Speaker(
                speaker_id=speaker_id,
                name=name,
                role=role,
                confidence=0.9,
                voice_signature=speaker_hash
            )
            
            self.logger.info(f"Identified new speaker: {name} ({speaker_id})")
        
        return self.speakers_db[speaker_id]
    
    async def generate_summary(self, transcript: str, speakers: Dict[str, Speaker]) -> MeetingSummary:
        """Generate mock meeting summary"""
        await asyncio.sleep(0.2)  # Simulate AI processing time
        
        # Mock summary generation
        summary_text = f"Mock meeting summary generated from {len(transcript.split())} words of transcript."
        
        key_points = [
            "Discussed project timeline and deliverables",
            "Reviewed current progress and milestones",
            "Identified potential risks and mitigation strategies",
            "Aligned on next steps and responsibilities"
        ]
        
        # Mock action items
        action_items = [
            ActionItem(
                description="Follow up on project requirements",
                assignee="Alice Johnson",
                due_date=(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                priority="high",
                confidence=0.85,
                source_text="Alice mentioned she would follow up on the requirements"
            ),
            ActionItem(
                description="Schedule technical review meeting",
                assignee="Bob Smith",
                due_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                priority="medium",
                confidence=0.78,
                source_text="Bob agreed to schedule the technical review"
            )
        ]
        
        next_steps = [
            "Finalize project scope and requirements",
            "Set up development environment",
            "Begin initial implementation phase"
        ]
        
        decisions_made = [
            "Approved use of React for frontend development",
            "Decided on weekly sprint cycles",
            "Confirmed project timeline and milestones"
        ]
        
        return MeetingSummary(
            summary_text=summary_text,
            key_points=key_points,
            action_items=action_items,
            next_steps=next_steps,
            decisions_made=decisions_made,
            confidence_score=0.82
        )
    
    async def extract_action_items(self, transcript: str) -> List[ActionItem]:
        """Extract mock action items from transcript"""
        await asyncio.sleep(0.1)
        
        # Simple pattern matching for action items
        action_patterns = [
            r"(\w+)\s+will\s+(.+?)(?:\.|$)",
            r"(\w+)\s+should\s+(.+?)(?:\.|$)",
            r"(\w+)\s+needs to\s+(.+?)(?:\.|$)",
            r"action item:?\s*(.+?)(?:\.|$)"
        ]
        
        action_items = []
        for pattern in action_patterns:
            matches = re.finditer(pattern, transcript, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    assignee, description = match.groups()
                    action_items.append(ActionItem(
                        description=description.strip(),
                        assignee=assignee.strip(),
                        confidence=0.7,
                        source_text=match.group(0)
                    ))
                else:
                    description = match.group(1)
                    action_items.append(ActionItem(
                        description=description.strip(),
                        confidence=0.6,
                        source_text=match.group(0)
                    ))
        
        return action_items[:5]  # Limit to 5 action items
    
    async def suggest_next_steps(self, transcript: str, summary: str) -> List[str]:
        """Generate mock next steps suggestions"""
        await asyncio.sleep(0.1)
        
        # Mock next steps based on common meeting patterns
        next_steps = [
            "Schedule follow-up meeting to review progress",
            "Document key decisions and share with stakeholders",
            "Begin implementation of discussed action items",
            "Set up regular check-ins to monitor progress"
        ]
        
        return next_steps[:3]  # Return top 3 suggestions
    
    async def cleanup(self) -> None:
        """Cleanup mock engine"""
        self.logger.info("Cleaning up mock transcription engine")
        self.speakers_db.clear()
        self.chunk_counter = 0


class GeminiTranscriptionEngine(BaseTranscriptionEngine):
    """Google Gemini-based transcription engine"""
    
    def __init__(self):
        super().__init__("gemini")
        self.api_key = None
        self.client = None
        self.speakers_db = {}
        self.model_name = "gemini-1.5-flash"
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Gemini transcription engine"""
        try:
            self.api_key = config.get('gemini_api_key')
            if not self.api_key:
                self.logger.error("Gemini API key not provided")
                return False
            
            # In real implementation, initialize Gemini client
            self.logger.info("Initializing Gemini transcription engine")
            await asyncio.sleep(0.2)  # Simulate API initialization
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini engine: {e}")
            return False
    
    async def transcribe_chunk(self, audio_chunk: AudioChunk) -> TranscriptChunk:
        """Transcribe using Gemini API"""
        try:
            # In real implementation, call Gemini API
            # For now, simulate API call with mock response
            await asyncio.sleep(0.1)  # Simulate API latency
            
            # Mock Gemini response
            mock_response = {
                'text': f"Transcribed text from Gemini for chunk {audio_chunk.chunk_id}",
                'confidence': 0.92,
                'language': 'en-US'
            }
            
            speaker = await self.identify_speaker(audio_chunk)
            
            chunk = TranscriptChunk(
                chunk_id=audio_chunk.chunk_id,
                text=mock_response['text'],
                speaker=speaker,
                start_time=audio_chunk.timestamp,
                end_time=audio_chunk.timestamp + audio_chunk.duration,
                confidence=mock_response['confidence'],
                is_final=True,
                language=mock_response['language']
            )
            
            return chunk
            
        except Exception as e:
            self.logger.error(f"Gemini transcription failed: {e}")
            raise
    
    async def identify_speaker(self, audio_chunk: AudioChunk) -> Speaker:
        """Identify speaker using Gemini voice analysis"""
        try:
            # In real implementation, use Gemini for speaker identification
            # For now, use simple heuristics
            speaker_id = f"gemini_speaker_{len(self.speakers_db) + 1}"
            
            if speaker_id not in self.speakers_db:
                self.speakers_db[speaker_id] = Speaker(
                    speaker_id=speaker_id,
                    name=f"Speaker {len(self.speakers_db) + 1}",
                    role=SpeakerRole.PARTICIPANT,
                    confidence=0.88
                )
            
            return self.speakers_db[speaker_id]
            
        except Exception as e:
            self.logger.error(f"Speaker identification failed: {e}")
            # Return unknown speaker
            return Speaker(
                speaker_id="unknown",
                name="Unknown Speaker",
                role=SpeakerRole.UNKNOWN,
                confidence=0.0
            )
    
    async def generate_summary(self, transcript: str, speakers: Dict[str, Speaker]) -> MeetingSummary:
        """Generate meeting summary using Gemini AI"""
        try:
            # Prepare speaker context
            speaker_context = "\n".join([
                f"- {speaker.name or speaker.speaker_id}: {speaker.role.value}"
                for speaker in speakers.values()
            ])
            
            prompt = f"""
            Please analyze this meeting transcript and provide a comprehensive summary.
            
            Meeting Participants:
            {speaker_context}
            
            Transcript:
            {transcript}
            
            Please provide:
            1. A concise summary (2-3 sentences)
            2. Key discussion points (3-5 bullet points)
            3. Action items with assignees and deadlines if mentioned
            4. Next steps and follow-up items
            5. Important decisions made
            
            Format your response as JSON with the following structure:
            {{
                "summary": "Brief meeting summary",
                "key_points": ["point 1", "point 2", ...],
                "action_items": [
                    {{
                        "description": "action description",
                        "assignee": "person name or null",
                        "due_date": "YYYY-MM-DD or null",
                        "priority": "high/medium/low"
                    }}
                ],
                "next_steps": ["step 1", "step 2", ...],
                "decisions": ["decision 1", "decision 2", ...]
            }}
            """
            
            # In real implementation, call Gemini API
            # For now, simulate with enhanced mock response
            await asyncio.sleep(0.3)  # Simulate API call
            
            # Mock Gemini response with realistic content
            mock_response = {
                "summary": "Team discussed project progress, identified key challenges, and aligned on next steps for the upcoming sprint.",
                "key_points": [
                    "Current sprint is 80% complete with minor delays in testing phase",
                    "New feature requirements were clarified with stakeholders",
                    "Resource allocation needs adjustment for next quarter",
                    "Technical debt items were prioritized for upcoming sprints"
                ],
                "action_items": [
                    {
                        "description": "Complete user acceptance testing for new features",
                        "assignee": "QA Team",
                        "due_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
                        "priority": "high"
                    },
                    {
                        "description": "Update project documentation with new requirements",
                        "assignee": "Product Manager",
                        "due_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                        "priority": "medium"
                    }
                ],
                "next_steps": [
                    "Finalize sprint deliverables and prepare for demo",
                    "Schedule stakeholder review meeting",
                    "Begin planning for next sprint cycle"
                ],
                "decisions": [
                    "Approved extension of current sprint by 2 days",
                    "Decided to prioritize performance optimization",
                    "Confirmed resource allocation for Q4"
                ]
            }
            
            # Convert to ActionItem objects
            action_items = []
            for item in mock_response.get("action_items", []):
                action_items.append(ActionItem(
                    description=item["description"],
                    assignee=item.get("assignee"),
                    due_date=item.get("due_date"),
                    priority=item.get("priority", "medium"),
                    confidence=0.88
                ))
            
            return MeetingSummary(
                summary_text=mock_response["summary"],
                key_points=mock_response["key_points"],
                action_items=action_items,
                next_steps=mock_response["next_steps"],
                decisions_made=mock_response["decisions"],
                confidence_score=0.88
            )
            
        except Exception as e:
            self.logger.error(f"Gemini summary generation failed: {e}")
            # Fallback to basic summary
            return MeetingSummary(
                summary_text="Meeting summary generation failed. Please review transcript manually.",
                key_points=["Summary generation error occurred"],
                action_items=[],
                next_steps=["Review meeting transcript manually"],
                decisions_made=[],
                confidence_score=0.0
            )
    
    async def extract_action_items(self, transcript: str) -> List[ActionItem]:
        """Extract action items using Gemini AI"""
        try:
            prompt = f"""
            Analyze this meeting transcript and extract all action items, tasks, and commitments.
            
            Transcript:
            {transcript}
            
            For each action item, identify:
            - What needs to be done (description)
            - Who is responsible (if mentioned)
            - When it should be completed (if mentioned)
            - Priority level (high/medium/low)
            
            Format as JSON array:
            [
                {{
                    "description": "task description",
                    "assignee": "person name or null",
                    "due_date": "YYYY-MM-DD or null",
                    "priority": "high/medium/low",
                    "source_text": "relevant quote from transcript"
                }}
            ]
            """
            
            # Simulate Gemini API call
            await asyncio.sleep(0.2)
            
            # Enhanced pattern matching for action items
            action_items = []
            
            # Look for explicit action patterns
            patterns = [
                r"(\w+)\s+will\s+(.+?)(?:\s+by\s+(\w+\s+\w+))?(?:\.|,|$)",
                r"(\w+)\s+should\s+(.+?)(?:\s+by\s+(\w+\s+\w+))?(?:\.|,|$)",
                r"(\w+)\s+needs to\s+(.+?)(?:\s+by\s+(\w+\s+\w+))?(?:\.|,|$)",
                r"action item:?\s*(.+?)(?:\s+assigned to\s+(\w+))?(?:\.|,|$)",
                r"todo:?\s*(.+?)(?:\s+for\s+(\w+))?(?:\.|,|$)"
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, transcript, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if len(groups) >= 2 and groups[1]:
                        action_items.append(ActionItem(
                            description=groups[1].strip(),
                            assignee=groups[0].strip() if groups[0] else None,
                            due_date=self._parse_due_date(groups[2]) if len(groups) > 2 and groups[2] else None,
                            priority="medium",
                            confidence=0.85,
                            source_text=match.group(0)
                        ))
            
            return action_items[:10]  # Limit to 10 action items
            
        except Exception as e:
            self.logger.error(f"Action item extraction failed: {e}")
            return []
    
    async def suggest_next_steps(self, transcript: str, summary: str) -> List[str]:
        """Suggest next steps using Gemini AI"""
        try:
            prompt = f"""
            Based on this meeting summary and transcript, suggest 3-5 logical next steps.
            
            Summary: {summary}
            
            Transcript: {transcript[:1000]}...
            
            Provide actionable next steps that would naturally follow from this meeting.
            Format as a simple JSON array of strings.
            """
            
            # Simulate Gemini API call
            await asyncio.sleep(0.15)
            
            # Generate contextual next steps
            next_steps = []
            
            # Analyze transcript for context clues
            if "follow up" in transcript.lower():
                next_steps.append("Schedule follow-up meeting to review progress")
            
            if "decision" in transcript.lower() or "decide" in transcript.lower():
                next_steps.append("Document decisions and communicate to stakeholders")
            
            if "action" in transcript.lower() or "task" in transcript.lower():
                next_steps.append("Begin execution of assigned action items")
            
            if "review" in transcript.lower():
                next_steps.append("Conduct thorough review of discussed items")
            
            # Add default next steps if none found
            if not next_steps:
                next_steps = [
                    "Distribute meeting notes to all participants",
                    "Set up tracking for action items and deadlines",
                    "Schedule check-in to monitor progress"
                ]
            
            return next_steps[:5]
            
        except Exception as e:
            self.logger.error(f"Next steps suggestion failed: {e}")
            return ["Review meeting outcomes and plan follow-up actions"]
    
    def _parse_due_date(self, date_text: str) -> Optional[str]:
        """Parse due date from natural language"""
        if not date_text:
            return None
        
        date_text = date_text.lower().strip()
        
        # Simple date parsing
        if "tomorrow" in date_text:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "next week" in date_text:
            return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        elif "friday" in date_text:
            # Find next Friday
            days_ahead = 4 - datetime.now().weekday()  # Friday is 4
            if days_ahead <= 0:
                days_ahead += 7
            return (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        return None
    
    async def cleanup(self) -> None:
        """Cleanup Gemini engine"""
        self.logger.info("Cleaning up Gemini transcription engine")
        self.speakers_db.clear()


class TranscriptionService:
    """
    Main transcription service for real-time audio processing
    """
    
    CHUNK_DURATION = 2.0  # seconds
    MAX_CHUNK_QUEUE_SIZE = 100
    ERROR_THRESHOLD = 5
    QUALITY_CHECK_INTERVAL = 10  # seconds
    
    def __init__(self, engine_type: str = "mock"):
        self.engine_type = engine_type
        self.engine: Optional[BaseTranscriptionEngine] = None
        self.sessions: Dict[str, TranscriptionSession] = {}
        self.audio_queues: Dict[str, asyncio.Queue] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.quality_monitors: Dict[str, asyncio.Task] = {}
        self.error_handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize transcription service"""
        try:
            # Create transcription engine
            if self.engine_type == "mock":
                self.engine = MockTranscriptionEngine()
            elif self.engine_type == "gemini":
                self.engine = GeminiTranscriptionEngine()
            else:
                raise ValueError(f"Unsupported engine type: {self.engine_type}")
            
            # Initialize engine
            success = await self.engine.initialize(config)
            if not success:
                raise Exception("Failed to initialize transcription engine")
            
            self.logger.info(f"Transcription service initialized with {self.engine_type} engine")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize transcription service: {e}")
            return False
    
    async def start_transcription(self, session_id: str, stream_id: str) -> TranscriptionSession:
        """Start transcription for a session"""
        try:
            if session_id in self.sessions:
                raise ValueError(f"Transcription session {session_id} already exists")
            
            # Create transcription session
            session = TranscriptionSession(
                session_id=session_id,
                stream_id=stream_id,
                is_active=True
            )
            
            self.sessions[session_id] = session
            
            # Create audio processing queue
            self.audio_queues[session_id] = asyncio.Queue(maxsize=self.MAX_CHUNK_QUEUE_SIZE)
            
            # Start processing task
            self.processing_tasks[session_id] = asyncio.create_task(
                self._process_audio_stream(session_id)
            )
            
            # Start quality monitoring
            self.quality_monitors[session_id] = asyncio.create_task(
                self._monitor_audio_quality(session_id)
            )
            
            self.logger.info(f"Started transcription for session {session_id}")
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to start transcription: {e}")
            raise
    
    async def process_audio_chunk(self, session_id: str, audio_data: bytes, 
                                timestamp: float, duration: float) -> bool:
        """Process incoming audio chunk"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Transcription session {session_id} not found")
            
            session = self.sessions[session_id]
            if not session.is_active:
                return False
            
            # Create audio chunk
            chunk_id = f"{session_id}_{int(timestamp * 1000)}"
            audio_chunk = AudioChunk(
                chunk_id=chunk_id,
                audio_data=audio_data,
                timestamp=timestamp,
                duration=duration
            )
            
            # Add to processing queue
            queue = self.audio_queues[session_id]
            if queue.full():
                # Remove oldest chunk if queue is full
                try:
                    queue.get_nowait()
                    self.logger.warning(f"Audio queue full for session {session_id}, dropping oldest chunk")
                except asyncio.QueueEmpty:
                    pass
            
            await queue.put(audio_chunk)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process audio chunk: {e}")
            await self._handle_error(session_id, e)
            return False
    
    async def get_transcript_chunks(self, session_id: str, 
                                 since_timestamp: Optional[float] = None) -> List[TranscriptChunk]:
        """Get transcript chunks for a session"""
        if session_id not in self.sessions:
            return []
        
        session = self.sessions[session_id]
        chunks = session.transcript_chunks
        
        if since_timestamp is not None:
            chunks = [chunk for chunk in chunks if chunk.start_time >= since_timestamp]
        
        return chunks
    
    async def get_full_transcript(self, session_id: str) -> str:
        """Get full transcript text for a session"""
        chunks = await self.get_transcript_chunks(session_id)
        return " ".join(chunk.text for chunk in chunks if chunk.is_final)
    
    async def generate_draft_summary(self, session_id: str) -> Optional[MeetingSummary]:
        """Generate AI-powered draft summary for a session"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session = self.sessions[session_id]
            
            # Get full transcript
            transcript = await self.get_full_transcript(session_id)
            if not transcript.strip():
                self.logger.warning(f"No transcript available for session {session_id}")
                return None
            
            # Generate summary using AI engine
            summary = await self.engine.generate_summary(transcript, session.speakers)
            
            # Store in session
            session.draft_summary = summary
            
            self.logger.info(f"Generated draft summary for session {session_id}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate draft summary: {e}")
            return None
    
    async def extract_action_items(self, session_id: str) -> List[ActionItem]:
        """Extract action items from session transcript"""
        try:
            if session_id not in self.sessions:
                return []
            
            transcript = await self.get_full_transcript(session_id)
            if not transcript.strip():
                return []
            
            action_items = await self.engine.extract_action_items(transcript)
            
            self.logger.info(f"Extracted {len(action_items)} action items for session {session_id}")
            return action_items
            
        except Exception as e:
            self.logger.error(f"Failed to extract action items: {e}")
            return []
    
    async def suggest_next_steps(self, session_id: str) -> List[str]:
        """Suggest next steps based on meeting content"""
        try:
            if session_id not in self.sessions:
                return []
            
            session = self.sessions[session_id]
            transcript = await self.get_full_transcript(session_id)
            
            if not transcript.strip():
                return []
            
            summary_text = ""
            if session.draft_summary:
                summary_text = session.draft_summary.summary_text
            
            next_steps = await self.engine.suggest_next_steps(transcript, summary_text)
            
            self.logger.info(f"Generated {len(next_steps)} next steps for session {session_id}")
            return next_steps
            
        except Exception as e:
            self.logger.error(f"Failed to suggest next steps: {e}")
            return []
    
    async def get_speaker_mapping(self, session_id: str) -> Dict[str, Speaker]:
        """Get speaker mapping for a session"""
        if session_id not in self.sessions:
            return {}
        
        return self.sessions[session_id].speakers.copy()
    
    async def stop_transcription(self, session_id: str) -> Dict[str, Any]:
        """Stop transcription for a session"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Transcription session {session_id} not found")
            
            session = self.sessions[session_id]
            session.is_active = False
            
            # Cancel processing tasks
            if session_id in self.processing_tasks:
                self.processing_tasks[session_id].cancel()
                del self.processing_tasks[session_id]
            
            if session_id in self.quality_monitors:
                self.quality_monitors[session_id].cancel()
                del self.quality_monitors[session_id]
            
            # Clean up queues
            if session_id in self.audio_queues:
                del self.audio_queues[session_id]
            
            # Generate session summary
            summary = {
                'session_id': session_id,
                'duration': time.time() - session.start_time,
                'total_chunks': len(session.transcript_chunks),
                'speakers_identified': len(session.speakers),
                'error_count': session.error_count,
                'final_quality': session.audio_quality.value
            }
            
            self.logger.info(f"Stopped transcription for session {session_id}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to stop transcription: {e}")
            raise
    
    async def _process_audio_stream(self, session_id: str):
        """Process audio stream for a session"""
        try:
            session = self.sessions[session_id]
            queue = self.audio_queues[session_id]
            
            while session.is_active:
                try:
                    # Get audio chunk from queue
                    audio_chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
                    
                    # Transcribe chunk
                    transcript_chunk = await self.engine.transcribe_chunk(audio_chunk)
                    
                    # Add to session
                    session.transcript_chunks.append(transcript_chunk)
                    
                    # Update speaker mapping
                    speaker_id = transcript_chunk.speaker.speaker_id
                    if speaker_id not in session.speakers:
                        session.speakers[speaker_id] = transcript_chunk.speaker
                    
                    self.logger.debug(f"Processed chunk for session {session_id}: {transcript_chunk.text[:50]}...")
                    
                except asyncio.TimeoutError:
                    # No audio chunks to process, continue
                    continue
                except Exception as e:
                    await self._handle_error(session_id, e)
                    
        except Exception as e:
            self.logger.error(f"Audio processing failed for session {session_id}: {e}")
            await self._handle_error(session_id, e)
    
    async def _monitor_audio_quality(self, session_id: str):
        """Monitor audio quality for a session"""
        try:
            session = self.sessions[session_id]
            
            while session.is_active:
                await asyncio.sleep(self.QUALITY_CHECK_INTERVAL)
                
                # Analyze recent chunks for quality indicators
                recent_chunks = [
                    chunk for chunk in session.transcript_chunks
                    if time.time() - chunk.end_time < self.QUALITY_CHECK_INTERVAL
                ]
                
                if recent_chunks:
                    avg_confidence = sum(chunk.confidence for chunk in recent_chunks) / len(recent_chunks)
                    
                    # Update quality based on confidence
                    if avg_confidence >= 0.9:
                        session.audio_quality = AudioQuality.EXCELLENT
                    elif avg_confidence >= 0.8:
                        session.audio_quality = AudioQuality.GOOD
                    elif avg_confidence >= 0.6:
                        session.audio_quality = AudioQuality.FAIR
                    elif avg_confidence >= 0.4:
                        session.audio_quality = AudioQuality.POOR
                    else:
                        session.audio_quality = AudioQuality.UNUSABLE
                    
                    self.logger.debug(f"Audio quality for session {session_id}: {session.audio_quality.value}")
                
        except Exception as e:
            self.logger.error(f"Quality monitoring failed for session {session_id}: {e}")
    
    async def _handle_error(self, session_id: str, error: Exception):
        """Handle transcription errors"""
        try:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.error_count += 1
                
                self.logger.warning(f"Transcription error in session {session_id}: {error}")
                
                # Check error threshold
                if session.error_count >= self.ERROR_THRESHOLD:
                    self.logger.error(f"Error threshold exceeded for session {session_id}, stopping transcription")
                    session.is_active = False
                
                # Call error handler if registered
                if session_id in self.error_handlers:
                    await self.error_handlers[session_id](session_id, error)
                    
        except Exception as e:
            self.logger.error(f"Error handling failed: {e}")
    
    def register_error_handler(self, session_id: str, handler: Callable):
        """Register error handler for a session"""
        self.error_handlers[session_id] = handler
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a transcription session"""
        if session_id not in self.sessions:
            return None
        
        return self.sessions[session_id].to_dict()
    
    async def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active transcription sessions"""
        active_sessions = {}
        for session_id, session in self.sessions.items():
            if session.is_active:
                active_sessions[session_id] = session.to_dict()
        
        return active_sessions
    
    async def cleanup(self):
        """Cleanup transcription service"""
        try:
            # Stop all active sessions
            for session_id in list(self.sessions.keys()):
                if self.sessions[session_id].is_active:
                    await self.stop_transcription(session_id)
            
            # Cleanup engine
            if self.engine:
                await self.engine.cleanup()
            
            self.logger.info("Transcription service cleaned up")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Utility functions for transcript processing
def merge_transcript_chunks(chunks: List[TranscriptChunk], 
                          speaker_merge_threshold: float = 2.0) -> List[TranscriptChunk]:
    """
    Merge consecutive transcript chunks from the same speaker
    
    Args:
        chunks: List of transcript chunks to merge
        speaker_merge_threshold: Maximum time gap (seconds) to merge chunks
        
    Returns:
        List of merged transcript chunks
    """
    if not chunks:
        return []
    
    merged_chunks = []
    current_chunk = chunks[0]
    
    for next_chunk in chunks[1:]:
        # Check if chunks can be merged
        same_speaker = current_chunk.speaker.speaker_id == next_chunk.speaker.speaker_id
        time_gap = next_chunk.start_time - current_chunk.end_time
        can_merge = same_speaker and time_gap <= speaker_merge_threshold
        
        if can_merge:
            # Merge chunks
            merged_text = f"{current_chunk.text} {next_chunk.text}".strip()
            merged_confidence = (current_chunk.confidence + next_chunk.confidence) / 2
            
            current_chunk = TranscriptChunk(
                chunk_id=f"merged_{current_chunk.chunk_id}_{next_chunk.chunk_id}",
                text=merged_text,
                speaker=current_chunk.speaker,
                start_time=current_chunk.start_time,
                end_time=next_chunk.end_time,
                confidence=merged_confidence,
                is_final=next_chunk.is_final,
                language=current_chunk.language
            )
        else:
            # Add current chunk and start new one
            merged_chunks.append(current_chunk)
            current_chunk = next_chunk
    
    # Add the last chunk
    merged_chunks.append(current_chunk)
    
    return merged_chunks


def format_transcript_with_timestamps(chunks: List[TranscriptChunk], 
                                    include_speakers: bool = True) -> str:
    """
    Format transcript chunks with timestamps and speaker names
    
    Args:
        chunks: List of transcript chunks
        include_speakers: Whether to include speaker names
        
    Returns:
        Formatted transcript string
    """
    formatted_lines = []
    
    for chunk in chunks:
        timestamp = time.strftime("%H:%M:%S", time.gmtime(chunk.start_time))
        
        if include_speakers and chunk.speaker.name:
            speaker_name = chunk.speaker.name
            line = f"[{timestamp}] {speaker_name}: {chunk.text}"
        else:
            line = f"[{timestamp}] {chunk.text}"
        
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)


def extract_speaker_statistics(chunks: List[TranscriptChunk]) -> Dict[str, Dict[str, Any]]:
    """
    Extract speaking statistics from transcript chunks
    
    Args:
        chunks: List of transcript chunks
        
    Returns:
        Dictionary with speaker statistics
    """
    speaker_stats = {}
    
    for chunk in chunks:
        speaker_id = chunk.speaker.speaker_id
        
        if speaker_id not in speaker_stats:
            speaker_stats[speaker_id] = {
                'name': chunk.speaker.name,
                'role': chunk.speaker.role.value,
                'total_duration': 0.0,
                'word_count': 0,
                'chunk_count': 0,
                'avg_confidence': 0.0,
                'confidence_sum': 0.0
            }
        
        stats = speaker_stats[speaker_id]
        duration = chunk.end_time - chunk.start_time
        word_count = len(chunk.text.split())
        
        stats['total_duration'] += duration
        stats['word_count'] += word_count
        stats['chunk_count'] += 1
        stats['confidence_sum'] += chunk.confidence
        stats['avg_confidence'] = stats['confidence_sum'] / stats['chunk_count']
    
    return speaker_stats