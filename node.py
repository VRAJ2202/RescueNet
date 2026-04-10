# node.py
import time
from schema import create_message, PRIORITY_ORDER
from storage import MessageStore
from transport import UDPTransport
import uuid
from triage import assess_emergency
from panic import detect_risk


class MeshNode:
    def __init__(self, node_id, port, peers):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.transport = UDPTransport(port=port)
        self.store = MessageStore(f"{node_id}.db")

        self.seen = set()
        self.outbox = []
        self._load_seen_from_db()

    def close(self):
        self.store.conn.close()


    def _load_seen_from_db(self):
        cur = self.store.conn.execute("SELECT message_id FROM messages")
        self.seen = {row[0] for row in cur.fetchall()}

    def send_emergency(self, text, priority="critical", ttl=5):
        # triage = assess_emergency(text)

        # msg = create_message(
        #     sender_id=self.node_id,
        #     msg_type="incident",
        #     priority=triage["severity"],
        #     payload={
        #         "text": text,
        #         "triage": triage
        #     },
        #     ttl=ttl
        # )
        # self._handle_outgoing(msg.__dict__)


        triage = assess_emergency(text)
        risk = detect_risk(text)
        if risk["risk"] == "high":
            print(f"[{self.node_id}] WARNING: {risk['warning']}")

        msg = create_message(
            sender_id=self.node_id,
            msg_type="incident",
            priority=triage["severity"],
            payload={
                "text": text,
                "triage": triage,
                "risk": risk
            },
            ttl=ttl
        )
        self._handle_outgoing(msg.__dict__)



    def _handle_outgoing(self, msg):
        if self.store.message_exists(msg["message_id"]):
            print(f"[{self.node_id}] duplicate ignored: {msg['message_id']}")
            return

        msg["route_trace"] = [self.port]
        msg["last_hop"] = self.port
        self.store.save_message(msg)
        self.seen.add(msg["message_id"])
        self.outbox.append(msg)

    def process_outbox(self):
        if not self.outbox:
            return

        self.outbox.sort(key=lambda msg: -PRIORITY_ORDER.get(msg.get("priority", "low"), 1))
        msg = self.outbox.pop(0)
        self._broadcast(msg)

    def _broadcast(self, msg):
        if msg["ttl"] <= 0:
            return

        peers = list(self.peers)
        if msg.get("priority") == "critical":
            peers = sorted(peers)

        for peer_port in peers:
            if msg.get("last_hop") == peer_port:
                continue
            
            text = msg.get("payload", {}).get("text", msg.get("payload", {}).get("status", "packet"))
            print(f"[{self.node_id}] forwarding to {peer_port}: {text}")
            outgoing = msg.copy()
            outgoing.setdefault("route_trace", [])
            outgoing["last_hop"] = self.port
            self.transport.send(outgoing, peer_port)

    def process_incoming(self):
        data, _ = self.transport.receive()
        if not data:
            return
        
        data.setdefault("route_trace", []).append(self.port)
        print(f"[{self.node_id}] route: {data.get('route_trace', [])}")

        if self.store.message_exists(data["message_id"]):
            print(f"[{self.node_id}] duplicate ignored: {data['message_id']}")
            return

        payload = data.get("payload", {})
        text = payload.get("text", payload.get("status", "packet"))

        self.seen.add(data["message_id"])
        self.store.save_message(data)

        print(f"[{self.node_id}] received: {text}")
        # print(data["payload"])

        if data.get("type") == "ack":
            return

        data["ttl"] -= 1
        if data["ttl"] > 0:
            data["last_hop"] = data.get("last_hop", self.port)
            self.outbox.append(data)