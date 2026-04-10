# test_sim.py
import threading
import time

from node import MeshNode
from schema import create_message


node_a = MeshNode("A", 5000, [5001])
node_b = MeshNode("B", 5001, [5000, 5002])
node_c = MeshNode("C", 5002, [5001])


def run_node(node):
    while True:
        node.process_incoming()
        node.process_outbox()
        time.sleep(0.1)


for n in [node_a, node_b, node_c]:
    threading.Thread(target=run_node, args=(n,), daemon=True).start()

time.sleep(1)



node_a.send_emergency("fire nearby, I will drive out")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    node_a.close()
    node_b.close()
    node_c.close()