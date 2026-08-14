"""Hash-chained ledger that simulates the on-chain trust-scoring logic
described in the paper. Each block links to the previous block's hash, so
any edit to historical events is detectable via is_valid().

contracts/TrustScore.sol implements the same scoring rules for a real EVM
deployment; this module lets the dashboard demo the behavior instantly,
without a wallet or testnet RPC connection.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field

SCORE_DELTAS = {
    "successful_delivery": 2.0,
    "on_time": 1.0,
    "late_delivery": -1.5,
    "dispute_raised": -3.0,
    "dispute_resolved_seller": 2.5,
    "dispute_resolved_buyer": -5.0,
    "fraud_flagged": -20.0,
}


@dataclass
class Block:
    index: int
    timestamp: float
    events: list
    previous_hash: str
    nonce: int = 0
    hash: str = field(default="", init=False)

    def __post_init__(self):
        self.hash = self.compute_hash()

    def compute_hash(self):
        payload = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "events": self.events,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class TrustChain:
    """Hash-chained ledger of transaction/dispute events with per-seller trust scores."""

    GENESIS_PREV_HASH = "0" * 64
    BASE_SCORE = 50.0

    def __init__(self):
        self.chain = [Block(0, time.time(), [{"type": "genesis"}], self.GENESIS_PREV_HASH)]
        self.trust_scores = {}

    def latest_block(self):
        return self.chain[-1]

    def record_event(self, seller_id, event_type, weight=1.0, metadata=None):
        event = {
            "seller_id": seller_id,
            "type": event_type,
            "weight": weight,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            events=[event],
            previous_hash=self.latest_block().hash,
        )
        self.chain.append(block)
        self._apply_score_delta(seller_id, event_type, weight)
        return block

    def _apply_score_delta(self, seller_id, event_type, weight):
        score = self.trust_scores.get(seller_id, self.BASE_SCORE)
        score += SCORE_DELTAS.get(event_type, 0.0) * weight
        self.trust_scores[seller_id] = max(0.0, min(100.0, score))

    def score(self, seller_id):
        return round(self.trust_scores.get(seller_id, self.BASE_SCORE), 2)

    def is_valid(self):
        for i in range(1, len(self.chain)):
            current, previous = self.chain[i], self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False, f"Block {i} hash mismatch — payload was tampered with after mining"
            if current.previous_hash != previous.hash:
                return False, f"Block {i} link to block {i - 1} is broken"
        return True, "Chain intact — no tampering detected"

    def to_records(self):
        records = []
        for block in self.chain:
            for event in block.events:
                records.append(
                    {
                        "block": block.index,
                        "hash": block.hash[:16] + "...",
                        "previous_hash": "genesis"
                        if block.previous_hash == self.GENESIS_PREV_HASH
                        else block.previous_hash[:16] + "...",
                        **event,
                    }
                )
        return records
