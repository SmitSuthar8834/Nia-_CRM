"""
Integration tests for TranscriptionService
Tests real-time transcription, speaker identification, and error handling
"""
import asyncio
import time
from unittest.mock import patch
from django.test import TestCase

from .transcription_service import (
    TranscriptionService,
    AudioChunk,
    Speaker,
    TranscriptChunk,
    AudioQuality,
    SpeakerRole,
    merge_transcript_chunks,
    format_transcript_with_timestamps,
    extract_speaker_statistics
)


class TranscriptionServiceIntegrationTest(TestCase):
    """Integration tests for TranscriptionService"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def tearDown(self):
        """Clean up test environment"""
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)
    
    def test_service_initialization(self):
        """Test transcription service initialization"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            config = {}
            
            result = await service.initialize(config)
            self.assertTrue(result)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_basic_transcription_workflow(self):
        """Test basic transcription workflow"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Start transcription session
            session = await service.start_transcription("test_session", "test_stream")
            self.assertEqual(session.session_id, "test_session")
            self.assertTrue(session.is_active)
            
            # Process audio chunks
            for i in range(3):
                audio_data = f"test_audio_{i}".encode()
                timestamp = time.time() + i * 2.0
                
                result = await service.process_audio_chunk(
                    "test_session", audio_data, timestamp, 2.0
                )
                self.assertTrue(result)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Get transcript chunks
            chunks = await service.get_transcript_chunks("test_session")
            self.assertGreater(len(chunks), 0)
            
            # Get full transcript
            transcript = await service.get_full_transcript("test_session")
            self.assertIsInstance(transcript, str)
            self.assertGreater(len(transcript), 0)
            
            # Get speaker mapping
            speakers = await service.get_speaker_mapping("test_session")
            self.assertGreater(len(speakers), 0)
            
            # Stop transcription
            summary = await service.stop_transcription("test_session")
            self.assertIn('session_id', summary)
            self.assertEqual(summary['session_id'], "test_session")
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Test processing audio for non-existent session
            result = await service.process_audio_chunk(
                "nonexistent", b"audio", time.time(), 2.0
            )
            self.assertFalse(result)
            
            # Test getting chunks for non-existent session
            chunks = await service.get_transcript_chunks("nonexistent")
            self.assertEqual(len(chunks), 0)
            
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_concurrent_sessions(self):
        """Test handling multiple concurrent sessions"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            # Start multiple sessions
            sessions = []
            for i in range(2):
                session = await service.start_transcription(f"session_{i}", f"stream_{i}")
                sessions.append(session)
            
            # Process audio for each session
            for i, session in enumerate(sessions):
                for j in range(2):
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
            self.assertEqual(len(active_sessions), 2)
            
            # Clean up
            for session in sessions:
                await service.stop_transcription(session.session_id)
            
            await service.cleanup()
        
        self.async_test(run_test())


class TranscriptUtilitiesTest(TestCase):
    """Test transcript utility functions"""
    
    def test_merge_transcript_chunks(self):
        """Test merging transcript chunks from same speaker"""
        speaker1 = Speaker("speaker_1", "Alice", SpeakerRole.HOST, 0.9)
        speaker2 = Speaker("speaker_2", "Bob", SpeakerRole.PARTICIPANT, 0.85)
        
        chunks = [
            TranscriptChunk("chunk_1", "Hello", speaker1, 0.0, 2.0, 0.9, True),
            TranscriptChunk("chunk_2", "everyone", speaker1, 2.5, 4.0, 0.85, True),
            TranscriptChunk("chunk_3", "How are you?", speaker2, 5.0, 7.0, 0.88, True),
        ]
        
        merged = merge_transcript_chunks(chunks, speaker_merge_threshold=1.0)
        
        # Should merge chunks 1&2 but not chunk 3 (different speaker)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].text, "Hello everyone")
        self.assertEqual(merged[1].text, "How are you?")
    
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
        
        bob_stats = stats["speaker_2"]
        self.assertEqual(bob_stats['name'], "Bob")
        self.assertEqual(bob_stats['role'], "participant")
        self.assertEqual(bob_stats['chunk_count'], 1)
        self.assertEqual(bob_stats['word_count'], 3)  # "Thank you Alice"


class AudioQualityTest(TestCase):
    """Test audio quality handling"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def tearDown(self):
        """Clean up test environment"""
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)
    
    def test_audio_quality_monitoring(self):
        """Test audio quality monitoring functionality"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("quality_test", "stream_1")
            
            # Process multiple audio chunks
            for i in range(5):
                audio_data = f"quality_test_chunk_{i}".encode()
                timestamp = time.time() + i * 0.5
                await service.process_audio_chunk("quality_test", audio_data, timestamp, 0.5)
            
            # Wait for processing and quality monitoring
            await asyncio.sleep(1.0)
            
            # Check session status includes quality information
            status = await service.get_session_status("quality_test")
            self.assertIn('audio_quality', status)
            self.assertIsInstance(status['audio_quality'], str)
            
            await service.stop_transcription("quality_test")
            await service.cleanup()
        
        self.async_test(run_test())
    
    def test_queue_overflow_handling(self):
        """Test handling of audio queue overflow"""
        async def run_test():
            service = TranscriptionService(engine_type="mock")
            await service.initialize({})
            
            session = await service.start_transcription("overflow_test", "stream_1")
            
            # Try to overflow the queue
            for i in range(service.MAX_CHUNK_QUEUE_SIZE + 5):
                audio_data = f"overflow_chunk_{i}".encode()
                timestamp = time.time() + i * 0.01
                
                result = await service.process_audio_chunk(
                    "overflow_test", audio_data, timestamp, 0.01
                )
                # Should handle overflow gracefully
                self.assertTrue(result)
            
            await service.stop_transcription("overflow_test")
            await service.cleanup()
        
        self.async_test(run_test())