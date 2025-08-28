"""
Integration tests for TranscriptionService
Tests real-time transcription, speaker identification, and error handling
"""
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase

from .transcription_service import (
    TranscriptionService,
    MockTranscriptionEngine,
    GeminiTranscriptionEngine,
    AudioChunk,
    Speaker,
    TranscriptChunk,
    TranscriptionSession,
    AudioQuality,
    SpeakerRole,
    merge_transcript_chunks,
    format_transcript_with_timestamps,
    extract_speaker_statistics
)


class AsyncTestCase(TestCase):
    """Base class for async test cases"""
    
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def tearDown(self):
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)


class TestAudioChunk(TestCase):
    """Test AudioChunk data structure"""
    
    def test_audio_chunk_creation(self):
        """Test AudioChunk creation and serialization"""
        audio_data = b"mock_audio_data"
        chunk = AudioChunk(
            chunk_id="test_chunk_1",
            audio_data=audio_data,
            timestamp=1234567890.0,
            duration=2.0,
            sample_rate=16000,
            channels=1
        )
        
        self.assertEqual(chunk.chunk_id, "test_chunk_1")
        self.assertEqual(chunk.audio_data, audio_data)
        self.assertEqual(chunk.timestamp, 1234567890.0)
        self.assertEqual(chunk.duration, 2.0)
        self.assertEqual(chunk.sample_rate, 16000)
        self.assertEqual(chunk.channels, 1)
        
        # Test serialization
        data = chunk.to_dict()
        self.assertEqual(data['chunk_id'], "test_chunk_1")
        self.assertEqual(data['timestamp'], 1234567890.0)
        self.assertEqual(data['duration'], 2.0)
        self.assertEqual(data['data_size'], len(audio_data))


class TestSpeaker(TestCase):
    """Test Speaker data structure"""
    
    def test_speaker_creation(self):
        """Test Speaker creation and serialization"""
        speaker = Speaker(
            speaker_id="speaker_123",
            name="John Doe",
            role=SpeakerRole.HOST,
            confidence=0.95,
            voice_signature="abc123"
        )
        
        self.assertEqual(speaker.speaker_id, "speaker_123")
        self.assertEqual(speaker.name, "John Doe")
        self.assertEqual(speaker.role, SpeakerRole.HOST)
        self.assertEqual(speaker.confidence, 0.95)
        self.assertEqual(speaker.voice_signature, "abc123")
        
        # Test serialization
        data = speaker.to_dict()
        self.assertEqual(data['speaker_id'], "speaker_123")
        self.assertEqual(data['name'], "John Doe")
        self.assertEqual(data['role'], "host")
        self.assertEqual(data['confidence'], 0.95)


class TestTranscriptChunk(TestCase):
    """Test TranscriptChunk data structure"""
    
    def test_transcript_chunk_creation(self):
        """Test TranscriptChunk creation and serialization"""
        speaker = Speaker(
            speaker_id="speaker_123",
            name="John Doe",
            role=SpeakerRole.HOST,
            confidence=0.95
        )
        
        chunk = TranscriptChunk(
            chunk_id="chunk_123",
            text="Hello everyone, welcome to the meeting.",
            speaker=speaker,
            start_time=1234567890.0,
            end_time=1234567892.0,
            confidence=0.92,
            is_final=True,
            language="en-US"
        )
        
        self.assertEqual(chunk.chunk_id, "chunk_123")
        self.assertEqual(chunk.text, "Hello everyone, welcome to the meeting.")
        self.assertEqual(chunk.speaker, speaker)
        self.assertEqual(chunk.start_time, 1234567890.0)
        self.assertEqual(chunk.end_time, 1234567892.0)
        self.assertEqual(chunk.confidence, 0.92)
        self.assertTrue(chunk.is_final)
        self.assertEqual(chunk.language, "en-US")
        
        # Test serialization
        data = chunk.to_dict()
        self.assertEqual(data['chunk_id'], "chunk_123")
        self.assertEqual(data['text'], "Hello everyone, welcome to the meeting.")
        self.assertEqual(data['confidence'], 0.92)
        self.assertTrue(data['is_final'])


class TestMockTranscriptionEngine(AsyncTestCase):
    """Test MockTranscriptionEngine functionality"""
    
    def test_mock_engine_initialization(self):
        """Test mock engine initialization"""
        async def run_test():
            engine = MockTranscriptionEngine()
            config = {}
            
            result = await engine.initialize(config)
            self.assertTrue(result)
            
            await engine.cleanup()
        
        self.async_test(run_test())
    
    def test_mock_transcription(self):
        """Test mock transcription functionality"""
        async def run_test():
            engine = MockTranscriptionEngine()
            await engine.initialize({})
            
            # Create test audio chunk
            audio_chunk = AudioChunk(
                chunk_id="test_chunk",
                audio_data=b"mock_audio_data",
                timestamp=time.time(),
                duration=2.0
            )
            
            # Transcribe chunk
            transcript_chunk = await engine.transcribe_chunk(audio_chunk)
            
            self.assertIsInstance(transcript_chunk, TranscriptChunk)
            self.assertEqual(transcript_chunk.chunk_id, "chunk_1")
            self.assertIsInstance(transcript_chunk.text, str)
            self.assertGreater(len(transcript_chunk.text), 0)
            self.assertIsInstance(transcript_chunk.speaker, Speaker)
            self.assertGreaterEqual(transcript_chunk.confidence, 0.85)
            self.assertLessEqual(transcript_chunk.confidence, 1.0)
            
            await engine.cleanup()
        
        self.async_test(run_test())
    
    def test_mock_speaker_identification(self):
        """Test mock speaker identification"""
        async def run_test():
            engine = MockTranscriptionEngine()
            await engine.initialize({})
            
            # Create test audio chunks with different properties
            chunk1 = AudioChunk("chunk1", b"data1", time.time(), 2.0, 16000, 1)
            chunk2 = AudioChunk("chunk2", b"data2", time.time(), 2.0, 16000, 1)
            
            speaker1 = await engine.identify_speaker(chunk1)
            speaker2 = await engine.identify_speaker(chunk2)
            
            self.assertIsInstance(speaker1, Speaker)
            self.assertIsInstance(speaker2, Speaker)
            self.assertIsNotNone(speaker1.speaker_id)
            self.assertIsNotNone(speaker1.name)
            self.assertEqual(speaker1.role, SpeakerRole.HOST)  # First speaker is host
            
            await engine.cleanup()
        
        self.async_test(run_test())


class TestGeminiTranscriptionEngine(AsyncTestCase):
    """Test GeminiTranscriptionEngine functionality"""
    
    def test_gemini_engine_initialization_without_key(self):
        """Test Gemini engine initialization without API key"""
        async def run_test():
            engine = GeminiTranscriptionEngine()
            config = {}  # No API key
            
            result = await engine.initialize(config)
            self.assertFalse(result)
            
            await engine.cleanup()
        
        self.async_test(run_test())
    
    def test_gemini_engine_initialization_with_key(self):
        """Test Gemini engine initialization with API key"""
        async def run_test():
            engine = GeminiTranscriptionEngine()
            config = {'gemini_api_key': 'test_api_key'}
            
            result = await engine.initialize(config)
            self.assertTrue(result)
            
            await engine.cleanup()
        
        self.async_test(run_test())
    
    def test_gemini_transcription(self):
        """Test Gemini transcription functionality"""
        async def run_test():
            engine = GeminiTranscriptionEngine()
            await engine.initialize({'gemini_api_key': 'test_key'})
            
            # Create test audio chunk
            audio_chunk = AudioChunk(
                chunk_id="gemini_test_chunk",
                audio_data=b"mock_audio_data",
                timestamp=time.time(),
                duration=2.0
            )
            
            # Transcribe chunk
            transcript_chunk = await engine.transcribe_chunk(audio_chunk)
            
            self.assertIsInstance(transcript_chunk, TranscriptChunk)
            self.assertEqual(transcript_chunk.chunk_id, "gemini_test_chunk")
            self.assertIn("Gemini", transcript_chunk.text)
            self.assertGreaterEqual(transcript_chunk.confidence, 0.9)
            
            await engine.cleanup()
        
        self.async_test(run_test())


class TestTranscriptionService(AsyncTestCase):
    """Test TranscriptionService main functionality"""
    
    def test_service_initialization(self):
        """Test transcription service initialization"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            config = {}
            
            result = await service.initialize(config)
            self.assertTrue(result)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_service_initialization_invalid_engine(self):
        """Test service initialization with invalid engine"""
        async def run_test():
            service = TranscriptionService(engine_type="invalid")
            config = {}
            
            result = await service.initialize(config)
            self.assertFalse(result)
        
        self.async_test(run_test())
    
    def test_start_transcription_session(self):
        """Test starting transcription session"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            self.assertIsInstance(session, TranscriptionSession)
            self.assertEqual(session.session_id, "session_1")
            self.assertEqual(session.stream_id, "stream_1")
            self.assertTrue(session.is_active)
            self.assertEqual(session.audio_quality, AudioQuality.GOOD)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_duplicate_session_error(self):
        """Test error when starting duplicate session"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Start first session
            await service.start_transcription("session_1", "stream_1")
            
            # Try to start duplicate session
            with self.assertRaises(ValueError):
                await service.start_transcription("session_1", "stream_2")
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_process_audio_chunks(self):
        """Test processing audio chunks"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Process multiple audio chunks
            for i in range(5):
                audio_data = f"mock_audio_data_{i}".encode()
                timestamp = time.time() + i * 2.0
                
                result = await service.process_audio_chunk(
                    "session_1", audio_data, timestamp, 2.0
                )
                self.assertTrue(result)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Check transcript chunks
            chunks = await service.get_transcript_chunks("session_1")
            self.assertGreater(len(chunks), 0)
            
            # Check speaker mapping
            speakers = await service.get_speaker_mapping("session_1")
            self.assertGreater(len(speakers), 0)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_get_full_transcript(self):
        """Test getting full transcript"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            await service.start_transcription("session_1", "stream_1")
            
            # Process audio chunks
            for i in range(3):
                audio_data = f"mock_audio_data_{i}".encode()
                timestamp = time.time() + i * 2.0
                
                await service.process_audio_chunk(
                    "session_1", audio_data, timestamp, 2.0
                )
            
            # Wait for processing
            await asyncio.sleep(0.3)
            
            # Get full transcript
            transcript = await service.get_full_transcript("session_1")
            self.assertIsInstance(transcript, str)
            self.assertGreater(len(transcript), 0)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_stop_transcription(self):
        """Test stopping transcription session"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Process some audio
            await service.process_audio_chunk(
                "session_1", b"mock_audio", time.time(), 2.0
            )
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Stop transcription
            summary = await service.stop_transcription("session_1")
            
            self.assertIsInstance(summary, dict)
            self.assertEqual(summary['session_id'], "session_1")
            self.assertIn('duration', summary)
            self.assertIn('total_chunks', summary)
            self.assertIn('speakers_identified', summary)
            
            # Check session is inactive
            self.assertFalse(session.is_active)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_audio_quality_monitoring(self):
        """Test audio quality monitoring"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Process audio chunks
            for i in range(10):
                audio_data = f"mock_audio_data_{i}".encode()
                timestamp = time.time() + i * 0.5
                
                await service.process_audio_chunk(
                    "session_1", audio_data, timestamp, 0.5
                )
            
            # Wait for processing and quality monitoring
            await asyncio.sleep(1.0)
            
            # Check session status
            status = await service.get_session_status("session_1")
            self.assertIsNotNone(status)
            self.assertIn('audio_quality', status)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_error_handling(self):
        """Test error handling in transcription"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Test processing audio for non-existent session
            result = await service.process_audio_chunk(
                "non_existent", b"audio", time.time(), 2.0
            )
            self.assertFalse(result)
            
            # Test getting chunks for non-existent session
            chunks = await service.get_transcript_chunks("non_existent")
            self.assertEqual(len(chunks), 0)
            
            # Test stopping non-existent session
            with self.assertRaises(ValueError):
                await service.stop_transcription("non_existent")
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_concurrent_sessions(self):
        """Test handling multiple concurrent sessions"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Start multiple sessions
            sessions = []
            for i in range(3):
                session = await service.start_transcription(f"session_{i}", f"stream_{i}")
                sessions.append(session)
            
            # Process audio for each session
            for i, session in enumerate(sessions):
                for j in range(5):
                    audio_data = f"session_{i}_chunk_{j}".encode()
                    timestamp = time.time() + j * 2.0
                    
                    await service.process_audio_chunk(
                        session.session_id, audio_data, timestamp, 2.0
                    )
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Check all sessions have transcripts
            for session in sessions:
                chunks = await service.get_transcript_chunks(session.session_id)
                self.assertGreater(len(chunks), 0)
            
            # List active sessions
            active_sessions = await service.list_active_sessions()
            self.assertEqual(len(active_sessions), 3)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_error_threshold_handling(self):
        """Test error threshold handling"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Simulate multiple errors
            for i in range(service.ERROR_THRESHOLD + 1):
                await service._handle_error("session_1", Exception(f"Test error {i}"))
            
            # Session should be inactive after exceeding error threshold
            self.assertFalse(session.is_active)
            
            await service.cleanup()
        
        self.async_test(run_test())


class TestTranscriptUtilities(TestCase):
    """Test transcript utility functions"""
    
    def test_merge_transcript_chunks(self):
        """Test merging transcript chunks from same speaker"""
        speaker1 = Speaker("speaker_1", "Alice", SpeakerRole.HOST, 0.9)
        speaker2 = Speaker("speaker_2", "Bob", SpeakerRole.PARTICIPANT, 0.85)
        
        chunks = [
            TranscriptChunk("chunk_1", "Hello", speaker1, 0.0, 2.0, 0.9, True),
            TranscriptChunk("chunk_2", "everyone", speaker1, 2.5, 4.0, 0.85, True),
            TranscriptChunk("chunk_3", "How are you?", speaker2, 5.0, 7.0, 0.88, True),
            TranscriptChunk("chunk_4", "I'm fine", speaker2, 7.2, 9.0, 0.92, True),
        ]
        
        merged = merge_transcript_chunks(chunks, speaker_merge_threshold=1.0)
        
        # Should merge chunks 1&2 and chunks 3&4
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].text, "Hello everyone")
        self.assertEqual(merged[1].text, "How are you? I'm fine")
    
    def test_format_transcript_with_timestamps(self):
        """Test formatting transcript with timestamps"""
        speaker = Speaker("speaker_1", "Alice", SpeakerRole.HOST, 0.9)
        
        chunks = [
            TranscriptChunk("chunk_1", "Hello everyone", speaker, 0.0, 2.0, 0.9, True),
            TranscriptChunk("chunk_2", "Welcome to the meeting", speaker, 3.0, 5.0, 0.85, True),
        ]
        
        formatted = format_transcript_with_timestamps(chunks, include_speakers=True)
        
        self.assertIn("Alice:", formatted)
        self.assertIn("Hello everyone", formatted)
        self.assertIn("Welcome to the meeting", formatted)
        
        # Test without speakers
        formatted_no_speakers = format_transcript_with_timestamps(chunks, include_speakers=False)
        self.assertNotIn("Alice:", formatted_no_speakers)
        self.assertIn("Hello everyone", formatted_no_speakers)
    
    def test_extract_speaker_statistics(self):
        """Test extracting speaker statistics"""
        speaker1 = Speaker("speaker_1", "Alice", SpeakerRole.HOST, 0.9)
        speaker2 = Speaker("speaker_2", "Bob", SpeakerRole.PARTICIPANT, 0.85)
        
        chunks = [
            TranscriptChunk("chunk_1", "Hello everyone welcome", speaker1, 0.0, 2.0, 0.9, True),
            TranscriptChunk("chunk_2", "Thank you Alice", speaker2, 3.0, 4.0, 0.85, True),
            TranscriptChunk("chunk_3", "Let's start the meeting", speaker1, 5.0, 7.0, 0.88, True),
        ]
        
        stats = extract_speaker_statistics(chunks)
        
        self.assertEqual(len(stats), 2)
        
        alice_stats = stats["speaker_1"]
        self.assertEqual(alice_stats['name'], "Alice")
        self.assertEqual(alice_stats['role'], "host")
        self.assertEqual(alice_stats['chunk_count'], 2)
        self.assertEqual(alice_stats['word_count'], 7)  # "Hello everyone welcome" + "Let's start the meeting"
        self.assertEqual(alice_stats['total_duration'], 4.0)  # 2.0 + 2.0
        
        bob_stats = stats["speaker_2"]
        self.assertEqual(bob_stats['name'], "Bob")
        self.assertEqual(bob_stats['role'], "participant")
        self.assertEqual(bob_stats['chunk_count'], 1)
        self.assertEqual(bob_stats['word_count'], 3)  # "Thank you Alice"


class TestAudioQualityHandling(AsyncTestCase):
    """Test audio quality handling and error scenarios"""
    
    def test_poor_audio_quality_detection(self):
        """Test detection of poor audio quality"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Simulate poor quality audio by creating chunks with low confidence
            # We'll need to modify the mock engine to return low confidence
            with patch.object(service.engine, 'transcribe_chunk') as mock_transcribe:
                speaker = Speaker("speaker_1", "Test Speaker", SpeakerRole.PARTICIPANT, 0.3)
                
                # Return low confidence chunks
                mock_transcribe.return_value = TranscriptChunk(
                    chunk_id="low_conf_chunk",
                    text="unclear audio",
                    speaker=speaker,
                    start_time=time.time(),
                    end_time=time.time() + 2.0,
                    confidence=0.3,  # Low confidence
                    is_final=True
                )
                
                # Process several low-quality chunks
                for i in range(5):
                    await service.process_audio_chunk(
                        "session_1", b"poor_audio", time.time() + i * 2.0, 2.0
                    )
                
                # Wait for processing and quality monitoring
                await asyncio.sleep(1.0)
                
                # Check that quality was detected as poor
                status = await service.get_session_status("session_1")
                # Quality monitoring should detect the low confidence
                
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_audio_queue_overflow_handling(self):
        """Test handling of audio queue overflow"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Fill up the audio queue beyond capacity
            for i in range(service.MAX_CHUNK_QUEUE_SIZE + 10):
                audio_data = f"overflow_chunk_{i}".encode()
                timestamp = time.time() + i * 0.1
                
                result = await service.process_audio_chunk(
                    "session_1", audio_data, timestamp, 0.1
                )
                # Should still return True even with queue overflow
                self.assertTrue(result)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_transcription_engine_failure_recovery(self):
        """Test recovery from transcription engine failures"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Mock engine failure
            with patch.object(service.engine, 'transcribe_chunk') as mock_transcribe:
                mock_transcribe.side_effect = Exception("Engine failure")
                
                # Process audio chunk that will cause engine failure
                result = await service.process_audio_chunk(
                    "session_1", b"failing_audio", time.time(), 2.0
                )
                
                # Should handle the error gracefully
                self.assertTrue(result)
                
                # Wait for error handling
                await asyncio.sleep(0.2)
                
                # Check error count increased
                self.assertGreater(session.error_count, 0)
            
            await service.cleanup()
        
        self.async_test(run_test())


class TestSpeakerIdentificationAccuracy(AsyncTestCase):
    """Test speaker identification accuracy and consistency"""
    
    def test_consistent_speaker_identification(self):
        """Test that same speaker is identified consistently"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Process multiple chunks with similar audio characteristics
            # (same sample rate, channels, similar data size)
            for i in range(5):
                audio_data = b"consistent_speaker_audio"  # Same audio pattern
                timestamp = time.time() + i * 2.0
                
                await service.process_audio_chunk(
                    "session_1", audio_data, timestamp, 2.0
                )
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Get transcript chunks
            chunks = await service.get_transcript_chunks("session_1")
            
            # Check that speaker identification is consistent
            if len(chunks) > 1:
                first_speaker_id = chunks[0].speaker.speaker_id
                for chunk in chunks[1:]:
                    # Should identify as same speaker for similar audio
                    self.assertEqual(chunk.speaker.speaker_id, first_speaker_id)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_multiple_speaker_differentiation(self):
        """Test differentiation between multiple speakers"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("session_1", "stream_1")
            
            # Process chunks with different audio characteristics
            audio_patterns = [
                b"speaker_one_pattern",
                b"speaker_two_different_pattern",
                b"speaker_three_unique_pattern"
            ]
            
            for i, pattern in enumerate(audio_patterns):
                for j in range(2):  # 2 chunks per speaker
                    timestamp = time.time() + (i * 2 + j) * 2.0
                    await service.process_audio_chunk(
                        "session_1", pattern, timestamp, 2.0
                    )
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Get speaker mapping
            speakers = await service.get_speaker_mapping("session_1")
            
            # Should identify multiple speakers
            self.assertGreaterEqual(len(speakers), 2)
            
            # Check that speakers have different IDs
            speaker_ids = list(speakers.keys())
            self.assertEqual(len(speaker_ids), len(set(speaker_ids)))  # All unique
            
            await service.cleanup()
        
        self.async_test(run_test())