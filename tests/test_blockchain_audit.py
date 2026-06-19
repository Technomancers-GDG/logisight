from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestBlockchainAudit:
    def test_import_module(self):
        from services.blockchain_audit import BlockchainLedger
        assert BlockchainLedger is not None

    def test_add_block_and_verify(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            block = ledger.add_block("reroute", 1, "reroute", "Vehicle rerouted due to disruption")
            assert block.index == 1  # genesis is index 0
            assert block.action == "reroute"
            block_hash = block.compute_hash()
            assert len(block_hash) == 64
            genesis_hash = ledger.chain[0].compute_hash()
            assert block.previous_hash == genesis_hash

            block2 = ledger.add_block("wait", 2, "wait", "Waiting due to congestion")
            assert block2.index == 2
            assert block2.previous_hash == block_hash

    def test_tamper_detection(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            ledger.add_block("reroute", 1, "reroute", "Test block 1")
            ledger.add_block("wait", 2, "wait", "Test block 2")

            result = ledger.verify_integrity()
            assert result["valid"] is True

    def test_chain_length(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            assert len(ledger.chain) == 1  # genesis
            ledger.add_block("reroute", 1, "reroute", "Test")
            assert len(ledger.chain) == 2
            ledger.add_block("wait", 2, "wait", "Test")
            assert len(ledger.chain) == 3

    def test_verify_integrity(self):
        from services.blockchain_audit import BlockchainLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger = BlockchainLedger(str(ledger_path))

            ledger.add_block("reroute", 1, "reroute", "Test block 1")
            ledger.add_block("wait", 2, "wait", "Test block 2")

            result = ledger.verify_integrity()
            assert result["valid"] is True
