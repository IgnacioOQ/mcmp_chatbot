
import os
import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.graph_utils import GraphUtils

TEST_GRAPH_FILE = "test_graph_correctness.md"

@pytest.fixture
def correctness_graph():
    # Create a small, known graph
    # Alpha <-> Beta <-> Gamma
    # Delta (isolated)
    content = """
### Nodes
| id | name | type |
| -- | -- | -- |
| id_alpha | Alpha | type_1 |
| id_beta | Beta | type_1 |
| id_gamma | Gamma | type_1 |
| id_delta | Delta | type_2 |

### Edges
| source | target | relationship |
| -- | -- | -- |
| id_alpha | id_beta | related |
| id_beta | id_gamma | related |
"""
    with open(TEST_GRAPH_FILE, "w") as f:
        f.write(content)

    yield TEST_GRAPH_FILE

    if os.path.exists(TEST_GRAPH_FILE):
        os.remove(TEST_GRAPH_FILE)

def test_get_subgraph_correctness(correctness_graph):
    gu = GraphUtils(graph_path=correctness_graph)

    # Test 1: Query "Alpha", max_depth=1
    # Match: Alpha. Neighbor: Beta.
    subgraph = gu.get_subgraph("Alpha", max_depth=1)
    node_ids = sorted([n['id'] for n in subgraph['nodes']])
    edge_pairs = sorted([(e['source'], e['target']) for e in subgraph['edges']])

    assert node_ids == ['id_alpha', 'id_beta']
    # Edge Alpha-Beta should be there
    assert len(edge_pairs) == 1
    assert edge_pairs[0] == ('id_alpha', 'id_beta')

    # Test 2: Query "Alpha", max_depth=2
    # Match: Alpha. Neighbors: Beta. Next Neighbors: Gamma.
    subgraph = gu.get_subgraph("Alpha", max_depth=2)
    node_ids = sorted([n['id'] for n in subgraph['nodes']])

    assert node_ids == ['id_alpha', 'id_beta', 'id_gamma']
    assert len(subgraph['edges']) == 2

    # Test 3: Isolated Node Delta
    subgraph = gu.get_subgraph("Delta", max_depth=1)
    node_ids = sorted([n['id'] for n in subgraph['nodes']])
    assert node_ids == ['id_delta']
    assert len(subgraph['edges']) == 0

    # Test 4: Query matching multiple nodes
    # "type_1" matches Alpha, Beta, Gamma.
    # Depth 0 -> Just them.
    subgraph = gu.get_subgraph("type_1", max_depth=0)
    node_ids = sorted([n['id'] for n in subgraph['nodes']])
    assert node_ids == ['id_alpha', 'id_beta', 'id_gamma']

if __name__ == "__main__":
    pass
