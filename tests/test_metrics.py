"""Tests for metric extraction."""

from graphoptim.analyzer.metrics import CFGMetrics, extract_cfg_metrics


class TestMetrics:
    """Test metric extraction against known values."""

    def test_simple_function_metrics(self):
        """Simple function should have low complexity."""
        code = """
def add(a, b):
    return a + b
"""
        metrics = extract_cfg_metrics(code, "add")
        assert isinstance(metrics, CFGMetrics)
        assert metrics.cyclomatic_complexity <= 2
        assert metrics.dead_nodes_count == 0
        assert metrics.lines_of_code >= 2

    def test_branching_complexity(self):
        """Function with branches should have higher CC."""
        code = """
def classify(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
"""
        metrics = extract_cfg_metrics(code, "classify")
        assert metrics.cyclomatic_complexity >= 2

    def test_loop_complexity(self):
        """Function with loops should increase CC."""
        code = """
def process(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item)
    return result
"""
        metrics = extract_cfg_metrics(code, "process")
        assert metrics.cyclomatic_complexity >= 2
        assert metrics.nodes > 0
        assert metrics.edges > 0

    def test_metrics_to_dict(self):
        """Metrics should serialize to dict correctly."""
        code = "def f(x): return x"
        metrics = extract_cfg_metrics(code, "f")
        d = metrics.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "cyclomatic_complexity" in d
        assert "dead_nodes_count" in d
        assert "lines_of_code" in d

    def test_node_edge_ratio(self):
        """Node-edge ratio should be computed."""
        code = """
def foo(x):
    if x > 0:
        return 1
    return 0
"""
        metrics = extract_cfg_metrics(code, "foo")
        assert metrics.node_edge_ratio >= 0

    def test_betweenness_centrality(self):
        """Betweenness centrality should be between 0 and 1."""
        code = """
def foo(x, y, z):
    if x > 0:
        a = 1
    else:
        a = 2
    if y > 0:
        b = 1
    else:
        b = 2
    return a + b
"""
        metrics = extract_cfg_metrics(code, "foo")
        assert 0 <= metrics.max_betweenness_centrality <= 1
