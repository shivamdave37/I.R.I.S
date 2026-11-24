"""Narrow Windows UI Automation actions bound to a fresh approved screen target."""

from dataclasses import dataclass
import hashlib
import importlib
import json
import re
import unicodedata

import approval_context
import config
import screen_capture


MAX_UI_TEXT = 500
SENSITIVE_TERMS = (
    "password", "credential", "sign in", "log in", "security", "permission", "administrator",
    "uac", "payment", "pay now", "billing", "checkout", "bank", "credit card", "debit card",
    "purchase", "financial", "transfer", "transaction", "delete", "remove", "uninstall",
    "format", "reset", "install", "authorize", "confirm", "user account control",
    "verification", "authentication", "approve", "allow", "continue",
)
CLICK_TYPES = {"Button", "Hyperlink", "MenuItem", "TabItem"}


@dataclass(frozen=True)
class PreparedTarget:
    """Accessibility identity shown in the approval prompt and checked again."""

    fingerprint: str
    description: str


def _process_name(process_id):
    """Read a target process basename using the standard Windows API."""
    if not isinstance(process_id, int) or isinstance(process_id, bool) or process_id <= 0:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.c_ulong(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                return None
            return buffer.value.rsplit("\\", 1)[-1].casefold()
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _uia_target(x, y):
    if not isinstance(x, int) or isinstance(x, bool) or not isinstance(y, int) or isinstance(y, bool):
        raise RuntimeError("UI coordinates must be integers.")
    try:
        pywinauto = importlib.import_module("pywinauto")
        target = pywinauto.Desktop(backend="uia").from_point(x, y)
        info = target.element_info
        control_type = str(info.control_type)
        name = str(info.name or "").strip()
        class_name = str(info.class_name or "").strip()
        auto_id = str(getattr(info, "automation_id", "") or "")
        process_id = getattr(info, "process_id", None)
        process_name = _process_name(process_id)
        runtime_id = getattr(info, "runtime_id", None)
        handle = getattr(info, "handle", None)
        rect = target.rectangle()
        bounds = [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)]
        visible = bool(target.is_visible())
        enabled = bool(target.is_enabled())
        raw = info.element
        is_password = getattr(raw, "CurrentIsPassword", None)
        if type(is_password) is not bool:
            raise RuntimeError("Iris cannot verify whether this control is a password field.")
    except ImportError as error:
        raise RuntimeError("UI automation is unavailable. Install the optional UI requirements.") from error
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError("Iris could not identify a stable Windows UI target.") from error

    if not visible or not enabled or not (bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]):
        raise RuntimeError("The UI target is hidden, disabled, or no longer at those coordinates.")
    if process_name not in config.UI_ALLOWED_PROCESS_NAMES:
        raise RuntimeError("This application is not in Iris's limited UI-control allowlist.")
    if not runtime_id and not handle:
        raise RuntimeError("The UI target has no stable identity; Iris refused the action.")

    labels = [name]
    parent = target
    for _ in range(12):
        try:
            parent = parent.parent()
            if parent is None:
                break
            parent_name = str(parent.element_info.name or "").strip()
            if parent_name:
                labels.append(parent_name)
        except Exception as error:
            raise RuntimeError("Iris could not verify the containing window for sensitive prompts.") from error
    else:
        raise RuntimeError("Iris could not verify the root application window; the action was refused.")
    combined = " ".join(labels).casefold()
    if is_password or any(term in combined for term in SENSITIVE_TERMS):
        raise RuntimeError("Iris will not interact with a password, security, financial, or destructive prompt. Handle it manually.")

    if control_type not in CLICK_TYPES | {"Edit"}:
        raise RuntimeError(f"This UI control type is not supported: {control_type or 'unknown'}.")
    if not name and not auto_id:
        raise RuntimeError("The UI target is ambiguous because it has no accessible name or automation ID.")

    identity = {
        "runtime_id": list(runtime_id) if isinstance(runtime_id, (tuple, list)) else str(runtime_id or ""),
        "handle": int(handle or 0), "process_id": int(process_id or 0), "context": labels,
        "control_type": control_type, "name": name,
        "class_name": class_name, "automation_id": auto_id, "bounds": bounds,
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=True).encode("ascii")
    ).hexdigest()
    safe_name = "".join(
        char for char in name[:120]
        if char in " \t" or unicodedata.category(char) != "Cc"
    )
    description = f"{control_type} {safe_name!r}" if safe_name else f"{control_type} automation ID {auto_id!r}"
    return target, control_type, fingerprint, description


def prepare_target(action, params):
    """Resolve a visible target before approval so its identity can be shown."""
    frame = screen_capture.latest_frame(params["frame_id"])
    if frame is None:
        raise RuntimeError("That screen capture is no longer current. Capture again before interacting.")
    x, y = params["x"], params["y"]
    if x >= frame.width or y >= frame.height:
        raise RuntimeError("The requested coordinates are outside the captured screen.")
    _target, control_type, fingerprint, description = _uia_target(x, y)
    if action == "ui_click" and control_type not in CLICK_TYPES:
        raise RuntimeError("Click is supported only for accessible buttons, links, tabs, or menu items.")
    if action == "ui_type" and control_type != "Edit":
        raise RuntimeError("Typing is supported only for a verified, non-password Windows Edit field.")
    return PreparedTarget(fingerprint, description)


def _validated_target(action, params, prepared):
    if not isinstance(prepared, PreparedTarget):
        raise RuntimeError("The approved target is missing; nothing was changed.")
    fresh = screen_capture._fresh_frame_for_ui(action, params)
    if fresh.frame_id != params["frame_id"]:
        raise RuntimeError("The screen changed after approval; nothing was changed. Capture again and review.")
    target, control_type, fingerprint, _description = _uia_target(params["x"], params["y"])
    if fingerprint != prepared.fingerprint:
        raise RuntimeError("The UI target changed after approval; nothing was changed. Review it again.")
    return target, control_type


def click_target(params, prepared):
    """Click one validated UI Automation control after its own typed approval."""
    approval_context.require("ui_click", params)
    try:
        target, _control_type = _validated_target("ui_click", params, prepared)
        target.click_input()
    except Exception as error:
        detail = str(error) if isinstance(error, RuntimeError) else "Windows did not accept the click request."
        return f"UI click failed: {detail}"
    return f"UI action unverified: click request sent to {prepared.description}; app state was not confirmed."


def type_into_target(params, prepared):
    """Set text only in a validated, accessible, non-password Edit control."""
    approval_context.require("ui_type", params)
    text = params.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_UI_TEXT:
        return "UI typing failed: text must be 1 to 500 characters."
    try:
        target, control_type = _validated_target("ui_type", params, prepared)
        if control_type != "Edit" or not hasattr(target, "set_edit_text"):
            return "UI typing failed: this control does not support safe text replacement."
        target.set_edit_text(text)
    except Exception as error:
        detail = str(error) if isinstance(error, RuntimeError) else "Windows did not accept the text request."
        return f"UI typing failed: {detail}"
    return f"UI action unverified: text request sent to {prepared.description}; app state was not confirmed."
