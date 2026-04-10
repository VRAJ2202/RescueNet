# schema.py
from dataclasses import dataclass, asdict
from typing import Dict, Any
import uuid
import time

PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

@dataclass
class Message:
    message_id: str
    sender_id: str
    type: str
    priority: str
    timestamp: int
    ttl: int
    payload: Dict[str, Any]

def create_message(sender_id: str, msg_type: str, priority: str, payload: Dict[str, Any], ttl: int = 5) -> Message:
    return Message(
        message_id=str(uuid.uuid4()),
        sender_id=sender_id,
        type=msg_type,
        priority=priority,
        timestamp=int(time.time()),
        ttl=ttl,
        payload=payload
    )

def to_dict(msg: Message) -> Dict[str, Any]:
    return asdict(msg)

def from_dict(data: Dict[str, Any]) -> Message:
    return Message(**data)


if __name__ == "__main__":
    msg = create_message(
        sender_id="A",
        msg_type="incident",
        priority="critical",
        payload={"text": "bike accident, heavy bleeding"},
        ttl=3
    )
    print(to_dict(msg))