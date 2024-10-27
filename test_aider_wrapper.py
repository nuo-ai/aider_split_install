import unittest
import asyncio
import tkinter as tk
from unittest.mock import MagicMock, patch
import sys
from queue import Queue
from aider_wrapper import (
    AiderVoiceGUI,
    AudioBufferManager,
    AudioProcessingError,
    PerformanceMonitor,
    WebSocketManager,
    VoiceCommandProcessor,
    ClipboardManager,
)

class AsyncMock(MagicMock):
    """Mock class that supports async methods and special method handling"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default return values for special methods
        self.__bool__.return_value = True
        
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __await__(self):
        async def dummy():
            return self
        return dummy().__await__()

    async def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

class TestAiderVoiceGUI(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        # Mock argument parser
        patcher = patch('argparse.ArgumentParser.parse_args')
        self.mock_parse_args = patcher.start()
        self.addCleanup(patcher.stop)

        mock_args = MagicMock()
        mock_args.voice_only = False
        mock_args.instructions = None
        mock_args.clipboard = False
        mock_args.chat_mode = "code"
        mock_args.suggest_shell_commands = False
        mock_args.model = None
        mock_args.gui = True
        mock_args.auto = False
        self.mock_parse_args.return_value = mock_args

        self.root = tk.Tk()
        self.app = AiderVoiceGUI(self.root)
        # Force GUI setup
        self.app.setup_gui()

    def tearDown(self):
        """Clean up after each test"""
        self.root.destroy()

    def test_init(self):
        """Test initialization of GUI components"""
        self.assertIsNotNone(self.app.root)
        self.assertIsNotNone(self.app.main_frame)
        self.assertIsNotNone(self.app.status_label)
        self.assertIsNotNone(self.app.input_text)
        self.assertIsNotNone(self.app.output_text)
        self.assertIsNotNone(self.app.transcription_text)
        self.assertIsNotNone(self.app.issues_text)

    def test_log_message(self):
        """Test logging messages to output text"""
        test_message = "Test message"
        self.app.log_message(test_message)
        output_text = self.app.output_text.get("1.0", tk.END).strip()
        self.assertEqual(output_text, test_message)

    def test_update_transcription(self):
        """Test updating transcription text"""
        test_text = "Test transcription"
        self.app.update_transcription(test_text, is_assistant=False)
        transcription = self.app.transcription_text.get("1.0", tk.END).strip()
        self.assertIn("🎤 " + test_text, transcription)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_connect_websocket(self, mock_connect):
        """Test websocket connection and message handling"""
        # Create async mock for websocket with proper boolean behavior
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.ping = AsyncMock()
        mock_ws.__bool__.return_value = True
        mock_connect.return_value = mock_ws

        async def run_test():
            # Start message handling tasks
            message_task = asyncio.create_task(self.app.handle_websocket_messages())
            queue_task = asyncio.create_task(self.app.process_audio_queue())

            try:
                result = await self.app.connect_websocket()
                self.assertTrue(result)
                self.assertEqual(self.app.ws, mock_ws)
                
                # Verify session.update was sent with correct data
                mock_ws.send.assert_called_once()
                call_args = mock_ws.send.call_args[0][0]
                self.assertIn("session.update", call_args)
                self.assertIn("model", call_args)
                
                # Additional assertions to verify connection state
                self.assertTrue(self.app.ws is not None)
                self.assertFalse(self.app.response_active)
                self.assertIsNone(self.app.last_transcript_id)
                self.assertEqual(len(self.app.audio_buffer), 0)
                
            finally:
                # Clean up tasks
                message_task.cancel()
                queue_task.cancel()
                try:
                    await message_task
                    await queue_task
                except asyncio.CancelledError:
                    pass

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_connect_websocket_failure(self, mock_connect):
        """Test websocket connection failure handling"""
        mock_connect.side_effect = Exception("Connection failed")

        async def run_test():
            result = await self.app.connect_websocket()
            self.assertFalse(result)
            self.assertIsNone(self.app.ws)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_websocket_timeout(self, mock_connect):
        """Test websocket timeout handling"""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_connect.return_value = mock_ws

        result = await self.app.connect_websocket()
        self.assertFalse(result)

    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_websocket_close(self, mock_connect):
        """Test websocket close handling"""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.close = AsyncMock()
        mock_connect.return_value = mock_ws

        result = await self.app.connect_websocket()
        self.assertTrue(result)
        await self.app.ws.close()
        mock_ws.close.assert_called_once()
        """Test websocket connection and message handling"""
        # Create async mock for websocket with proper boolean behavior
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.ping = AsyncMock()
        mock_ws.__bool__.return_value = True
        mock_connect.return_value = mock_ws

        async def run_test():
            # Start message handling tasks
            message_task = asyncio.create_task(self.app.handle_websocket_messages())
            queue_task = asyncio.create_task(self.app.process_audio_queue())

            try:
                result = await self.app.connect_websocket()
                self.assertTrue(result)
                self.assertEqual(self.app.ws, mock_ws)
                
                # Verify session.update was sent with correct data
                mock_ws.send.assert_called_once()
                call_args = mock_ws.send.call_args[0][0]
                self.assertIn("session.update", call_args)
                self.assertIn("model", call_args)
                
                # Additional assertions to verify connection state
                self.assertTrue(self.app.ws is not None)
                self.assertFalse(self.app.response_active)
                self.assertIsNone(self.app.last_transcript_id)
                self.assertEqual(len(self.app.audio_buffer), 0)
                
            finally:
                # Clean up tasks
                message_task.cancel()
                queue_task.cancel()
                try:
                    await message_task
                    await queue_task
                except asyncio.CancelledError:
                    pass

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

class TestAudioBufferManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.buffer_manager = AudioBufferManager(
            max_size=1024,
            chunk_size=256,
            sample_rate=24000
        )

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.buffer_manager.max_size, 1024)
        self.assertEqual(self.buffer_manager.chunk_size, 256)
        self.assertEqual(self.buffer_manager.sample_rate, 24000)
        self.assertEqual(len(self.buffer_manager.buffer), 0)
        self.assertEqual(self.buffer_manager.stats["drops"], 0)
        self.assertEqual(self.buffer_manager.stats["overflows"], 0)

    def test_get_usage(self):
        """Test buffer usage calculation"""
        self.buffer_manager.buffer = bytearray(512)
        self.assertEqual(self.buffer_manager.get_usage(), 0.5)
        
        self.buffer_manager.buffer = bytearray(1024)
        self.assertEqual(self.buffer_manager.get_usage(), 1.0)
        
        self.buffer_manager.buffer = bytearray()
        self.assertEqual(self.buffer_manager.get_usage(), 0.0)

    def test_get_chunks_empty_queue(self):
        """Test getting chunks from empty queue"""
        test_queue = Queue()
        chunks = self.buffer_manager.get_chunks(test_queue)
        self.assertEqual(len(chunks), 0)

    def test_get_chunks_with_data(self):
        """Test getting chunks with valid data"""
        test_queue = Queue()
        test_data = [b"test1", b"test2", b"test3"]
        for data in test_data:
            test_queue.put(data)
            
        chunks = self.buffer_manager.get_chunks(test_queue)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks, test_data)

    def test_get_chunks_overflow(self):
        """Test chunk overflow handling"""
        test_queue = Queue()
        # Put data larger than max_size
        test_queue.put(b"x" * (self.buffer_manager.max_size + 100))
        
        chunks = self.buffer_manager.get_chunks(test_queue)
        self.assertEqual(len(chunks), 0)
        self.assertEqual(self.buffer_manager.stats["overflows"], 1)

    def test_combine_chunks(self):
        """Test chunk combination"""
        test_chunks = [b"test1", b"test2", b"test3"]
        combined = self.buffer_manager.combine_chunks(test_chunks)
        self.assertEqual(combined, b"test1test2test3")

    def test_combine_chunks_error(self):
        """Test error handling in combine_chunks"""
        test_chunks = [b"test1", None, b"test3"]
        with self.assertRaises(AudioProcessingError):
            self.buffer_manager.combine_chunks(test_chunks)
        self.assertEqual(self.buffer_manager.stats["drops"], 1)

class TestPerformanceMonitor(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.metrics = ["cpu", "memory", "latency"]
        self.monitor = PerformanceMonitor(self.metrics)

    def test_init(self):
        """Test initialization"""
        self.assertEqual(list(self.monitor.metrics.keys()), self.metrics)
        for metric in self.metrics:
            self.assertEqual(self.monitor.metrics[metric], [])

    def test_update(self):
        """Test metric updates"""
        self.monitor.update("cpu", 50)
        self.assertEqual(self.monitor.metrics["cpu"], [50])

    def test_get_metrics(self):
        """Test getting metric averages"""
        self.monitor.update("cpu", 50)
        self.monitor.update("cpu", 60)
        metrics = self.monitor.get_metrics()
        self.assertEqual(metrics["cpu"], 55)

class TestVoiceCommandProcessor(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.parent = MagicMock()
        self.processor = VoiceCommandProcessor(self.parent)

    def test_init(self):
        """Test initialization"""
        self.assertIsInstance(self.processor.commands, list)
        self.assertEqual(len(self.processor.commands), 0)

    def test_preprocess_command(self):
        """Test command preprocessing"""
        # Test stripping whitespace
        self.assertEqual(self.processor.preprocess_command("  test  "), "test")
        # Test converting to lowercase
        self.assertEqual(self.processor.preprocess_command("TEST"), "test")
        # Test combined effects
        self.assertEqual(self.processor.preprocess_command("  TEST  "), "test")

    def test_validate_command(self):
        """Test command validation"""
        # Test empty command
        self.assertFalse(self.processor.validate_command(""))
        self.assertFalse(self.processor.validate_command("   "))
        # Test valid command
        self.assertTrue(self.processor.validate_command("test command"))


class TestWebSocketManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.parent = MagicMock()
        self.manager = WebSocketManager(self.parent)
        self.mock_ws = AsyncMock()
        self.mock_ws.ping = AsyncMock()
        self.parent.ws = self.mock_ws

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.manager.connection_state, "disconnected")
        self.assertEqual(self.manager.reconnect_attempts, 0)
        self.assertEqual(self.manager.max_reconnect_attempts, 5)
        self.assertEqual(self.manager.ping_interval, 30)

    async def test_check_connection_success(self):
        """Test successful connection check"""
        self.manager.connection_state = "connected"
        await self.manager.check_connection()
        self.mock_ws.ping.assert_called_once()
        self.assertEqual(self.manager.connection_state, "connected")

    async def test_check_connection_failure(self):
        """Test connection check failure"""
        self.manager.connection_state = "connected"
        self.mock_ws.ping.side_effect = websockets.exceptions.WebSocketException()
        await self.manager.check_connection()
        self.assertEqual(self.manager.connection_state, "disconnected")

    async def test_monitor_connection(self):
        """Test connection monitoring"""
        self.manager.check_connection = AsyncMock()
        self.manager.attempt_reconnect = AsyncMock()
        
        # Test monitoring connected state
        self.manager.connection_state = "connected"
        self.manager.last_ping_time = 0
        monitor_task = asyncio.create_task(self.manager.monitor_connection())
        
        await asyncio.sleep(0.1)
        self.manager.check_connection.assert_called()
        
        # Test monitoring disconnected state
        self.manager.connection_state = "disconnected"
        await asyncio.sleep(0.1)
        self.manager.attempt_reconnect.assert_called()
        
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    async def test_attempt_reconnect_success(self):
        """Test successful reconnection attempt"""
        async def mock_connect():
            return True
        self.parent.connect_websocket = mock_connect
        
        await self.manager.attempt_reconnect()
        self.assertEqual(self.manager.connection_state, "connected")
        self.assertEqual(self.manager.reconnect_attempts, 0)

    async def test_attempt_reconnect_failure(self):
        """Test failed reconnection attempt"""
        async def mock_connect():
            raise websockets.exceptions.WebSocketException()
        self.parent.connect_websocket = mock_connect
        
        await self.manager.attempt_reconnect()
        self.assertEqual(self.manager.connection_state, "disconnected")
        self.assertEqual(self.manager.reconnect_attempts, 1)

    async def test_max_reconnect_attempts(self):
        """Test maximum reconnection attempts"""
        self.manager.reconnect_attempts = self.manager.max_reconnect_attempts
        await self.manager.attempt_reconnect()
        self.parent.log_message.assert_called_with("❌ Max reconnection attempts reached")

    def run_async_test(self, coro):
        """Helper method to run async tests"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_check_connection_sync(self):
        """Test check_connection using sync wrapper"""
        self.run_async_test(self.test_check_connection_success())
        self.run_async_test(self.test_check_connection_failure())

    def test_monitor_connection_sync(self):
        """Test monitor_connection using sync wrapper"""
        self.run_async_test(self.test_monitor_connection())

    def test_attempt_reconnect_sync(self):
        """Test attempt_reconnect using sync wrapper"""
        self.run_async_test(self.test_attempt_reconnect_success())
        self.run_async_test(self.test_attempt_reconnect_failure())

class TestClipboardManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.parent = MagicMock()
        self.parent.interface_state = {}
        self.parent.log_message = MagicMock()
        self.manager = ClipboardManager(self.parent)

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.manager.previous_content, "")
        self.assertFalse(self.manager.monitoring)
        self.assertIsNone(self.manager.monitoring_task)
        self.assertEqual(self.manager.update_interval, 0.5)
        self.assertEqual(self.manager.max_content_size, 1024 * 1024)
        self.assertEqual(self.manager.error_count, 0)
        self.assertEqual(self.manager.max_errors, 3)

    def test_detect_content_type(self):
        """Test content type detection"""
        # Test code detection
        code_samples = [
            "def test_function():",
            "class TestClass:",
            "import sys",
            "function myFunc() {",
        ]
        for code in code_samples:
            self.assertEqual(self.manager.detect_content_type(code), "code")

        # Test URL detection
        url_samples = [
            "http://example.com",
            "https://test.org",
            "www.example.com",
        ]
        for url in url_samples:
            self.assertEqual(self.manager.detect_content_type(url), "url")

        # Test text detection
        text_samples = [
            "Regular text",
            "123456",
            "No special formatting",
        ]
        for text in text_samples:
            self.assertEqual(self.manager.detect_content_type(text), "text")

    def test_looks_like_code(self):
        """Test code detection"""
        self.assertTrue(self.manager.looks_like_code("def test():"))
        self.assertTrue(self.manager.looks_like_code("class MyClass:"))
        self.assertTrue(self.manager.looks_like_code("import os"))
        self.assertFalse(self.manager.looks_like_code("regular text"))

    def test_looks_like_url(self):
        """Test URL detection"""
        self.assertTrue(self.manager.looks_like_url("http://example.com"))
        self.assertTrue(self.manager.looks_like_url("https://test.org"))
        self.assertTrue(self.manager.looks_like_url("www.example.com"))
        self.assertFalse(self.manager.looks_like_url("not a url"))

    def test_process_code(self):
        """Test code processing"""
        input_code = "def test():\n    print('test')  \n\n"
        expected = "def test():\n    print('test')\n"
        self.assertEqual(self.manager.process_code(input_code), expected)

    def test_process_text(self):
        """Test text processing"""
        input_text = "  test text  \n"
        expected = "test text"
        self.assertEqual(self.manager.process_text(input_text), expected)

    def test_process_url(self):
        """Test URL processing"""
        input_url = "  https://example.com  \n"
        expected = "https://example.com"
        self.assertEqual(self.manager.process_url(input_url), expected)

    @patch('pyperclip.paste')
    def test_get_current_content(self, mock_paste):
        """Test getting current clipboard content"""
        # Test code content
        mock_paste.return_value = "def test():\n    pass\n"
        result = self.manager.get_current_content()
        self.assertEqual(result, "def test():\n    pass\n")

        # Test URL content
        mock_paste.return_value = "https://example.com"
        result = self.manager.get_current_content()
        self.assertEqual(result, "https://example.com")

        # Test text content
        mock_paste.return_value = "regular text"
        result = self.manager.get_current_content()
        self.assertEqual(result, "regular text")

if __name__ == '__main__':
    unittest.main(verbosity=2)
