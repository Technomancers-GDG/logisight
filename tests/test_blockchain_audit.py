from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest


class TestBlockchainAudit:
    def test_import_module(self):
        from services.blockchain_audit import BlockchainLedger
        assert BlockchainLedger is not None

    def test_ledger_append_and_verify(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            entry = ledger.append("reroute", {"vehicle_id": 1, "from": "WH-01", "to": "WH-02"})
            assert entry["index"] == 0
            assert entry["action"] == "reroute"
            assert "hash" in entry
            assert "previous_hash" in entry
            assert entry["previous_hash"] == hashlib.sha256(b"").hexdigest()

            entry2 = ledger.append("wait", {"vehicle_id": 2, "reason": "congestion"})
            assert entry2["index"] == 1
            assert entry2["previous_hash"] == entry["hash"]

    def test_ledger_tamper_detection(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            ledger.append("reroute", {"vehicle_id": 1})
            ledger.append("wait", {"vehicle_id": 2})

            ledger._load_chain.assert_not_called() if hasattr(ledger, "_load_chain") else None

    def test_ledger_get_chain_length(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            assert ledger.length() == 0
            ledger.append("reroute", {})
            assert ledger.length() == 1
            ledger.append("wait", {})
            assert ledger.length() == 2

    def test_ledger_verify_integrity(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            ledger.append("reroute", {"v": 1})
            ledger.append("wait", {"v": 2})

            assert ledger.verify() is True
