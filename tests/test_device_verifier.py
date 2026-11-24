"""Unit tests for device profile detection, solution verification, and AI self-correction."""

import unittest
from unittest.mock import patch

import ai
import device_profile
import solution_verifier


class DeviceProfileTests(unittest.TestCase):
    """Test device hardware and OS profile gathering."""

    def test_default_profile_contains_user_pc_specs(self):
        """Current profile reflects the user's HP Laptop with 32GB RAM and Intel CPU."""
        dev = device_profile.CURRENT_DEVICE
        self.assertEqual(dev.os_name, "Windows")
        self.assertIn("11", dev.os_version)
        self.assertIn("HP Laptop", dev.system_model)
        self.assertIn("Intel", dev.processor)
        self.assertFalse(dev.has_cuda)
        self.assertGreaterEqual(dev.ram_gb, 16.0)

    def test_profile_summary_string(self):
        """Summary produces a clean, readable one-line hardware summary."""
        dev = device_profile.DeviceProfile(
            os_full="Microsoft Windows 11 Home Single Language",
            architecture="AMD64",
            processor="12th Gen Intel(R) Core(TM) i5-1235U",
            ram_gb=32.0,
            has_cuda=False,
            python_version="3.13.1",
        )
        summary = dev.summary()
        self.assertIn("Windows 11", summary)
        self.assertIn("12th Gen Intel", summary)
        self.assertIn("32GB", summary)
        self.assertIn("No CUDA", summary)


class SolutionVerifierTests(unittest.TestCase):
    """Test pre-flight compatibility verification against device constraints."""

    def setUp(self):
        self.profile = device_profile.DeviceProfile(
            os_name="Windows",
            os_full="Microsoft Windows 11 Home Single Language",
            processor="12th Gen Intel(R) Core(TM) i5-1235U",
            gpu="Intel(R) Iris(R) Xe Graphics (Integrated, No CUDA)",
            has_cuda=False,
            ram_gb=32.0,
        )

    def test_compatible_windows_solution_passes(self):
        """Standard Windows PowerShell or portable Python commands pass verification."""
        code = "In PowerShell run: Get-Process | Where-Object { $_.CPU -gt 10 }"
        res = solution_verifier.verify_solution(code, self.profile)
        self.assertTrue(res.is_compatible)
        self.assertEqual(res.issues, [])

    def test_flags_linux_apt_package_manager(self):
        """Commands using 'sudo apt install' are flagged as incompatible on Windows."""
        sol = "Run `sudo apt-get install ffmpeg` to install the package."
        res = solution_verifier.verify_solution(sol, self.profile)
        self.assertFalse(res.is_compatible)
        self.assertTrue(any("apt" in issue.lower() for issue in res.issues))
        self.assertTrue(any("winget" in tip.lower() for tip in res.suggestions))

    def test_flags_brew_on_windows(self):
        """Homebrew macOS/Linux commands are flagged."""
        sol = "Use brew install nodejs."
        res = solution_verifier.verify_solution(sol, self.profile)
        self.assertFalse(res.is_compatible)
        self.assertTrue(any("homebrew" in issue.lower() for issue in res.issues))

    def test_flags_systemctl_and_unix_paths(self):
        """Linux services and /etc paths are caught on Windows."""
        sol = "Check /etc/nginx/nginx.conf and run systemctl restart nginx"
        res = solution_verifier.verify_solution(sol, self.profile)
        self.assertFalse(res.is_compatible)
        self.assertTrue(any("systemctl" in issue.lower() for issue in res.issues))
        self.assertTrue(any("/etc/" in issue for issue in res.issues))

    def test_flags_cuda_on_integrated_intel_gpu(self):
        """CUDA calls are caught when the device has integrated Intel graphics."""
        sol = "import torch\nx = torch.randn(10, 10).cuda()\nprint(x)"
        res = solution_verifier.verify_solution(sol, self.profile)
        self.assertFalse(res.is_compatible)
        self.assertTrue(any("cuda" in issue.lower() for issue in res.issues))
        self.assertTrue(any("cpu" in tip.lower() or "directml" in tip.lower() for tip in res.suggestions))

    def test_flags_oversized_70b_model_for_ram(self):
        """Recommending a 70B parameter model is flagged for interactive desktop RAM."""
        sol = "Download the 70b llama model weights and load them into memory."
        res = solution_verifier.verify_solution(sol, self.profile)
        self.assertFalse(res.is_compatible)
        self.assertTrue(any("70b" in issue.lower() for issue in res.issues))

    def test_correction_prompt_generation(self):
        """The feedback prompt includes the target PC specs and specific failure reasons."""
        res = solution_verifier.VerificationResult(
            is_compatible=False,
            issues=["Uses 'sudo' on Windows", "Requires CUDA but device has Intel Xe"],
            suggestions=["use PowerShell as Administrator", "use device='cpu'"],
        )
        prompt = solution_verifier.generate_correction_prompt(res.issues, res.suggestions, self.profile)
        self.assertIn("Target PC Profile", prompt)
        self.assertIn("Windows", prompt)
        self.assertIn("sudo", prompt)
        self.assertIn("CUDA", prompt)


class AiSelfCorrectionTests(unittest.TestCase):
    """Test that ai.ask() catches incompatible outputs and triggers self-correction."""

    def setUp(self):
        ai.clear_history()

    def tearDown(self):
        ai.clear_history()

    def test_self_correction_loop_replaces_incompatible_answer(self):
        """When AI initially returns 'sudo apt install', Iris sends feedback and returns the corrected answer."""
        first_incompatible = "Run `sudo apt install ffmpeg` to install FFmpeg."
        second_corrected = "On Windows 11, run: `winget install Gyan.FFmpeg` in PowerShell."

        calls = []

        def mock_ask_gemini(messages, system_prompt=None):
            calls.append(messages)
            if len(calls) == 1:
                return True, first_incompatible
            return True, second_corrected

        with patch("ai._ask_gemini", side_effect=mock_ask_gemini), \
                patch.dict("os.environ", {"IRIS_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}):
            reply = ai.ask("How to install ffmpeg?")

        # Verifies that two model calls were made (first proposal, then self-correction)
        self.assertEqual(len(calls), 2)
        # Verifies the final answer contains the corrected solution and verification note
        self.assertIn("winget install", reply)
        self.assertIn("Auto-Corrected for your PC", reply)

    def test_compatible_answer_does_not_trigger_retry(self):
        """A clean, compatible answer is returned on the first turn without retry."""
        calls = []

        def mock_ask_gemini(messages, system_prompt=None):
            calls.append(messages)
            return True, "Python 3 is already installed. Check with 'python --version'."

        with patch("ai._ask_gemini", side_effect=mock_ask_gemini), \
                patch.dict("os.environ", {"IRIS_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}):
            reply = ai.ask("Check python")

        self.assertEqual(len(calls), 1)
        self.assertIn("python --version", reply)


if __name__ == "__main__":
    unittest.main()
