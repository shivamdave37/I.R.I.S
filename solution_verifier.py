"""Verify AI proposed solutions, commands, and code against device hardware and OS."""

from dataclasses import dataclass, field
import re
from typing import List, Tuple
from device_profile import DeviceProfile, CURRENT_DEVICE


@dataclass
class VerificationResult:
    """Outcome of checking a solution against device capabilities."""

    is_compatible: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def feedback_message(self) -> str:
        """Format a clear prompt explaining why the solution failed verification."""
        reasons = "; ".join(self.issues)
        tips = "; ".join(self.suggestions)
        msg = f"Compatibility check failed: {reasons}."
        if tips:
            msg += f" Suggested adjustments: {tips}."
        return msg


def verify_solution(solution_text: str, profile: DeviceProfile = None) -> VerificationResult:
    """Inspect code or command text for hardware, OS, and tool incompatibilities."""
    if profile is None:
        profile = CURRENT_DEVICE

    text = str(solution_text or "")
    issues = []
    suggestions = []

    # 1. Operating System checks (Windows vs Linux/macOS)
    if profile.os_name.lower() == "windows":
        # Linux package managers
        linux_pkg_mgrs = [
            (r"\bsudo\s+apt(?:-get)?\b", "apt/apt-get", "use winget or pip instead"),
            (r"\bbrew\s+install\b", "Homebrew", "use winget or chocolatey on Windows"),
            (r"\byum\s+install\b", "yum", "use winget on Windows"),
            (r"\bpacman\s+-S\b", "pacman", "use winget on Windows"),
        ]
        for pattern, name, tip in linux_pkg_mgrs:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Contains Linux package command '{name}', but this machine runs {profile.os_full}")
                suggestions.append(tip)

        # Linux-only administrative and service commands
        linux_cmds = [
            (r"\bsystemctl\b", "systemctl", "use Windows 'Get-Service' or 'sc.exe'"),
            (r"\bjournalctl\b", "journalctl", "use Windows Event Viewer or Get-WinEvent"),
            (r"\bchmod\s+[+]?x\b", "chmod", "Windows does not use POSIX permission bits"),
            (r"\bchown\b", "chown", "use icacls on Windows for permissions"),
            (r"\bsudo\b", "sudo", "run PowerShell as Administrator instead of sudo"),
        ]
        for pattern, name, tip in linux_cmds:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Uses '{name}' command which is not natively available in Windows PowerShell")
                suggestions.append(tip)

        # Unix filesystem absolute paths
        unix_paths = [r"/etc/", r"/var/log/", r"/usr/local/", r"/usr/bin/"]
        for upath in unix_paths:
            if re.search(upath, text):
                issues.append(f"References Unix directory '{upath}' instead of Windows paths (e.g., C:\\...)")
                suggestions.append("use Windows paths or %APPDATA%/environment variables")

        # Bash environment variable syntax vs PowerShell
        if re.search(r"\bexport\s+[A-Za-z_][A-Za-z0-9_]*=", text):
            issues.append("Uses bash 'export VAR=value' syntax")
            suggestions.append("use PowerShell syntax: $env:VAR = 'value'")

    # 2. GPU & Acceleration checks (No NVIDIA CUDA)
    if not profile.has_cuda:
        cuda_indicators = [
            (r"\btorch\.cuda\b", "torch.cuda", "use device='cpu' or DirectML/OpenVINO"),
            (r"\.cuda\(\)", ".cuda() call", "use .to('cpu')"),
            (r"--gpus\s+all", "NVIDIA Docker/GPU flag", "system has integrated Intel GPU; remove GPU flag"),
            (r"\bimport\s+tensorrt\b", "TensorRT", "TensorRT requires an NVIDIA GPU; use ONNX or OpenVINO"),
            (r"device\s*=\s*['\"]cuda['\"]", "device='cuda'", "set device='cpu'"),
        ]
        for pattern, name, tip in cuda_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Requires NVIDIA CUDA ({name}), but PC has {profile.gpu}")
                suggestions.append(tip)

    # 3. Heavy Resource / Memory constraints
    # Check if a model size is way too large for 32GB RAM (e.g. 70B parameter raw weights)
    if re.search(r"\b70b\b", text, re.IGNORECASE) and re.search(r"\b(?:llama|qwen|model|weights)\b", text, re.IGNORECASE):
        issues.append("Recommends a 70B parameter model which exceeds the safe unified/RAM budget for interactive use")
        suggestions.append("recommend a 7B, 8B, or 14B quantized model (GGUF Q4_K_M) that fits comfortably in 32GB RAM")

    # Deduplicate while preserving order
    unique_issues = list(dict.fromkeys(issues))
    unique_suggestions = list(dict.fromkeys(suggestions))

    return VerificationResult(
        is_compatible=len(unique_issues) == 0,
        issues=unique_issues,
        suggestions=unique_suggestions,
    )


def generate_correction_prompt(issues: List[str], suggestions: List[str], profile: DeviceProfile = None) -> str:
    """Generate a prompt instruction to guide the AI to correct its solution."""
    if profile is None:
        profile = CURRENT_DEVICE

    reasons_str = "\n- ".join(issues)
    suggestions_str = "\n- ".join(suggestions)
    return (
        f"The previous solution is incompatible with the user's specific PC hardware and OS.\n"
        f"Target PC Profile: {profile.summary()}\n"
        f"Shell: Windows PowerShell 5.1 / 7, Command Prompt\n"
        f"Incompatibilities detected:\n- {reasons_str}\n"
        f"Required corrections:\n- {suggestions_str}\n"
        f"Please rewrite the solution so it works natively and reliably on this exact machine."
    )
