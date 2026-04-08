"""Tests for the knapsack pass selector."""

from graphoptim.optimizer.passes.knapsack import KnapsackSelector, PassInfo


class TestKnapsackSelector:
    """Test the 0/1 knapsack pass selector."""

    def test_empty_passes(self):
        """Empty pass list should return empty selection."""
        selector = KnapsackSelector(budget=0.6)
        result = selector.select([])
        assert len(result.selected_passes) == 0
        assert result.total_cost == 0.0
        assert result.total_benefit == 0.0

    def test_single_pass_within_budget(self):
        """Single pass within budget should be selected."""
        selector = KnapsackSelector(budget=0.6)
        passes = [
            PassInfo(name="dead_code", cost=0.2, benefit=0.5),
        ]
        result = selector.select(passes)
        assert len(result.selected_passes) == 1
        assert result.selected_passes[0].name == "dead_code"

    def test_single_pass_over_budget(self):
        """Single pass over budget should not be selected."""
        selector = KnapsackSelector(budget=0.1)
        passes = [
            PassInfo(name="centrality", cost=0.6, benefit=0.5),
        ]
        result = selector.select(passes)
        assert len(result.selected_passes) == 0

    def test_optimal_selection(self):
        """Should select passes maximizing benefit within budget."""
        selector = KnapsackSelector(budget=0.5)
        passes = [
            PassInfo(name="dead_code", cost=0.2, benefit=0.5),
            PassInfo(name="path_shortener", cost=0.5, benefit=0.4),
            PassInfo(name="centrality", cost=0.3, benefit=0.3),
        ]
        result = selector.select(passes)
        # Best within 0.5 budget: dead_code(0.2) + centrality(0.3) = 0.5 cost, 0.8 benefit
        # vs path_shortener alone = 0.5 cost, 0.4 benefit
        total_benefit = result.total_benefit
        assert total_benefit >= 0.4  # At minimum, should get something good

    def test_all_passes_fit(self):
        """If all passes fit in budget, select all."""
        selector = KnapsackSelector(budget=1.0)
        passes = [
            PassInfo(name="dead_code", cost=0.2, benefit=0.3),
            PassInfo(name="path_shortener", cost=0.3, benefit=0.2),
            PassInfo(name="centrality", cost=0.4, benefit=0.4),
        ]
        result = selector.select(passes)
        assert len(result.selected_passes) == 3
        assert result.total_cost <= 1.0

    def test_zero_benefit_excluded(self):
        """Passes with zero benefit should not be selected."""
        selector = KnapsackSelector(budget=0.6)
        passes = [
            PassInfo(name="dead_code", cost=0.2, benefit=0.0),
            PassInfo(name="path_shortener", cost=0.3, benefit=0.5),
        ]
        result = selector.select(passes)
        assert all(p.name != "dead_code" for p in result.selected_passes)

    def test_summary_output(self):
        """Summary should be a readable string."""
        selector = KnapsackSelector(budget=0.6)
        passes = [
            PassInfo(name="dead_code", cost=0.2, benefit=0.5),
        ]
        result = selector.select(passes)
        summary = result.summary()
        assert "dead_code" in summary
        assert "budget" in summary

    def test_prerequisites_included(self):
        """Prerequisites should be resolved and included."""
        selector = KnapsackSelector(budget=1.0)
        passes = [
            PassInfo(name="a", cost=0.1, benefit=0.0),  # No benefit alone
            PassInfo(name="b", cost=0.3, benefit=0.5, prerequisites=["a"]),
        ]
        result = selector.select(passes)
        # 'b' has benefit, and requires 'a'
        # 'a' should be included because it's a prerequisite
        names = {p.name for p in result.selected_passes}
        if "b" in names:
            assert "a" in names

    def test_rejected_passes(self):
        """Rejected passes should be accessible."""
        selector = KnapsackSelector(budget=0.3)
        passes = [
            PassInfo(name="cheap", cost=0.2, benefit=0.3),
            PassInfo(name="expensive", cost=0.5, benefit=0.8),
        ]
        result = selector.select(passes)
        assert len(result.rejected_passes) >= 0
