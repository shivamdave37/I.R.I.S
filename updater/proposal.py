"""Represent and persist one reviewed Iris code-update proposal."""

from dataclasses import asdict, dataclass, field
import json
import os
import re
import tempfile
import threading

import config


_PROPOSAL_LOCK = threading.Lock()


@dataclass
class Proposal:
    """Store the full candidate files, review evidence, and approval state."""

    id: str
    reason: str
    requested_by: str
    files: dict
    diff: str
    status: str
    hash: str
    revisions: int = 0
    base_hashes: dict = field(default_factory=dict)
    risk_summary: dict = field(default_factory=dict)
    test_result: dict = field(default_factory=dict)


def _proposal_folder():
    """Return the project's private ignored proposal folder."""
    project = os.path.abspath(config.PROJECT_FOLDER)
    expected_data = os.path.join(project, "data")
    if (os.path.abspath(config.DATA_FOLDER) != expected_data or os.path.islink(project)
            or os.path.islink(expected_data)):
        raise ValueError("Proposal storage must stay in the project's data folder.")
    folder = os.path.join(expected_data, "update_proposals")
    if os.path.islink(folder):
        raise ValueError("Proposal storage cannot be a symbolic link.")
    return folder


def save_proposal(proposal):
    """Write one proposal atomically under data/update_proposals."""
    if not re.fullmatch(r"[a-f0-9]{12}", proposal.id):
        raise ValueError("Invalid proposal identifier.")
    folder = _proposal_folder()
    path = os.path.join(folder, proposal.id + ".json")
    os.makedirs(folder, exist_ok=True)
    with _PROPOSAL_LOCK:
        descriptor, temporary = tempfile.mkstemp(prefix="proposal_", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as proposal_file:
                json.dump(asdict(proposal), proposal_file, indent=2, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
    return path


def load_proposals():
    """Load valid saved proposals without trusting their file names or JSON shape."""
    try:
        folder = _proposal_folder()
    except ValueError:
        return proposals
    proposals = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return proposals
    for name in names:
        if not re.fullmatch(r"[a-f0-9]{12}\.json", name):
            continue
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8") as proposal_file:
                stored = json.load(proposal_file)
            proposal = Proposal(**stored)
            if proposal.id + ".json" == name and isinstance(proposal.files, dict):
                proposals.append(proposal)
        except (OSError, ValueError, TypeError):
            continue
    return proposals


def find_proposal(identifier):
    """Return one saved proposal by its exact identifier."""
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{12}", identifier):
        return None
    return next((proposal for proposal in load_proposals() if proposal.id == identifier), None)
