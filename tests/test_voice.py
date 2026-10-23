"""Hardware-free tests for the Stage 2 voice features."""

import io
import queue
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

import main
import voice


class VoiceTests(unittest.TestCase):
    """Check voice failures and speaker queue behavior without audio devices."""

    def test_listen_returns_none_on_timeout(self):
        """Return None when the microphone receives no speech before timeout."""
        recognizer = Mock()
        recognizer.listen.side_effect = TimeoutError("silence")
        microphone = MagicMock()
        speech = Mock(Recognizer=Mock(return_value=recognizer), Microphone=Mock(return_value=microphone))
        with patch("voice._load_speech_recognition", return_value=speech):
            self.assertIsNone(voice.listen())
        recognizer.listen.assert_called_once_with(microphone.__enter__.return_value, timeout=5, phrase_time_limit=8)

    def test_listen_returns_none_on_recognition_error(self):
        """Return None when online speech recognition fails."""
        recognizer = Mock()
        recognizer.listen.return_value = "audio"
        recognizer.recognize_google.side_effect = RuntimeError("offline")
        speech = Mock(Recognizer=Mock(return_value=recognizer), Microphone=Mock(return_value=MagicMock()))
        with patch("voice._load_speech_recognition", return_value=speech):
            self.assertIsNone(voice.listen())

    def test_speak_queues_text(self):
        """Queue speech text without starting a real audio engine in the test."""
        pending_speech = queue.Queue()
        with patch.object(voice, "_speaker_queue", pending_speech):
            with patch.object(voice, "_start_speaker") as start_speaker:
                voice.speak("Hello there")
        start_speaker.assert_called_once_with()
        self.assertEqual(pending_speech.get_nowait(), "Hello there")

    def test_shutdown_stops_the_speaker_thread(self):
        """Send the stop marker and wait for the speaker worker to finish."""
        pending_speech = queue.Queue()
        speaker_thread = Mock()
        speaker_thread.is_alive.side_effect = [True, True, False]
        with patch.object(voice, "_speaker_queue", pending_speech):
            with patch.object(voice, "_speaker_lock", threading.Lock()):
                with patch.object(voice, "_speaker_thread", speaker_thread):
                    voice.shutdown()
        self.assertIsNone(pending_speech.get_nowait())
        speaker_thread.join.assert_called_once_with(timeout=10)

    def test_both_mode_falls_back_to_typed_input(self):
        """Use typed input when voice recognition returns None in both mode."""
        with patch("main.config.MODE", "both"):
            with patch("main.setup_logging"), patch("main.log_action"):
                with patch("builtins.input", return_value="exit") as typed_input:
                    with patch("main.voice.listen", return_value=None) as microphone:
                        with patch("main.voice.wait_until_done"), patch("main.voice.speak") as speaker:
                            with patch("main.voice.shutdown"):
                                with patch("sys.stdout", new_callable=io.StringIO) as output:
                                    main.run()
        microphone.assert_called_once_with()
        typed_input.assert_called_once_with("You: ")
        speaker.assert_called_once_with("Goodbye!")
        self.assertIn("Please type your command", output.getvalue())

    def test_typed_mode_does_not_use_voice(self):
        """Keep typed mode independent of the microphone and speaker."""
        with patch("main.config.MODE", "typed"):
            with patch("main.setup_logging"), patch("main.log_action"):
                with patch("builtins.input", return_value="exit"):
                    with patch("main.voice.listen") as microphone:
                        with patch("main.voice.speak") as speaker:
                            with patch("main.voice.wait_until_done") as wait_for_speech:
                                with patch("main.voice.shutdown") as shutdown:
                                    with patch("sys.stdout", new_callable=io.StringIO):
                                        main.run()
        microphone.assert_not_called()
        speaker.assert_not_called()
        wait_for_speech.assert_called_once_with()
        shutdown.assert_called_once_with()

    def test_listen_waits_for_speech_to_finish(self):
        """Ensure listen calls wait_until_done before opening the microphone."""
        with patch("voice.wait_until_done") as wait_speech:
            with patch("voice._load_speech_recognition", side_effect=RuntimeError("stop")):
                voice.listen()
        wait_speech.assert_called_once_with()

    def test_speak_skips_empty_or_none(self):
        """Do not start background speaker thread or queue speech for empty text."""
        with patch.object(voice, "_start_speaker") as start_speaker:
            voice.speak(None)
            voice.speak("")
            voice.speak("   ")
        start_speaker.assert_not_called()

    def test_both_mode_uses_voice_when_recognized(self):
        """Execute spoken command in both mode without prompting for typed input."""
        with patch("main.config.MODE", "both"):
            with patch("main.setup_logging"), patch("main.log_action"):
                with patch("builtins.input") as typed_input:
                    with patch("main.voice.listen", return_value="exit") as microphone:
                        with patch("main.voice.wait_until_done"), patch("main.voice.speak") as speaker:
                            with patch("main.voice.shutdown"):
                                with patch("sys.stdout", new_callable=io.StringIO):
                                    main.run()
        microphone.assert_called_once_with()
        typed_input.assert_not_called()
        speaker.assert_called_once_with("Goodbye!")

    def test_voice_mode_retries_on_silence(self):
        """Voice-only mode speaks a prompt and continues listening when silence occurs."""
        with patch("main.config.MODE", "voice"):
            with patch("main.setup_logging"), patch("main.log_action"):
                with patch("main.voice.listen", side_effect=[None, "exit"]) as microphone:
                    with patch("main.voice.wait_until_done"), patch("main.voice.speak") as speaker:
                        with patch("main.voice.shutdown"):
                            with patch("sys.stdout", new_callable=io.StringIO):
                                main.run()
        self.assertEqual(microphone.call_count, 2)
        speaker.assert_any_call("I couldn't hear you. Please try again.")
        speaker.assert_any_call("Goodbye!")

    def test_mode_case_insensitivity(self):
        """Accept mode settings with different casing or surrounding whitespace."""
        with patch("main.config.MODE", " BOTH "):
            with patch("main.setup_logging"), patch("main.log_action"):
                with patch("main.voice.listen", return_value="exit"):
                    with patch("main.voice.wait_until_done"), patch("main.voice.speak"):
                        with patch("main.voice.shutdown"):
                            with patch("sys.stdout", new_callable=io.StringIO):
                                main.run()



if __name__ == "__main__":
    unittest.main()
