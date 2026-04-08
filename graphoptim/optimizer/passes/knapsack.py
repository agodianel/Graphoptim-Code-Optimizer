"""
Knapsack Pass Selector for GraphOptim.

Solves the 0/1 Knapsack problem to select the optimal subset of
optimization passes within a user-defined risk budget.

This is the key innovation — instead of running all passes blindly,
the selector maximizes total improvement benefit while respecting
a maximum total cost (risk) budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class OptimizationPass(Protocol):
    """Protocol for optimization passes."""

    name: str
    cost: float  # 0.0 to 1.0 — estimated code change risk
    benefit: float  # 0.0 to 1.0 — estimated complexity reduction


@dataclass
class PassInfo:
    """Information about an optimization pass for the knapsack solver."""

    name: str
    cost: float
    benefit: float
    prerequisites: list[str] = field(default_factory=list)
    pass_obj: object = None  # Reference to the actual pass object


@dataclass
class KnapsackResult:
    """Result of the knapsack pass selection."""

    selected_passes: list[PassInfo]
    total_cost: float
    total_benefit: float
    budget: float
    all_passes: list[PassInfo]

    @property
    def rejected_passes(self) -> list[PassInfo]:
        """Passes that were not selected."""
        selected_names = {p.name for p in self.selected_passes}
        return [p for p in self.all_passes if p.name not in selected_names]

    def summary(self) -> str:
        """Human-readable summary of the selection."""
        lines = [
            f"Knapsack Pass Selection (budget={self.budget:.2f})",
            f"Total cost: {self.total_cost:.2f} / {self.budget:.2f}",
            f"Total benefit: {self.total_benefit:.2f}",
            "",
            "Selected passes:",
        ]
        for p in self.selected_passes:
            lines.append(f"  ✓ {p.name} (cost={p.cost:.2f}, benefit={p.benefit:.2f})")

        if self.rejected_passes:
            lines.append("")
            lines.append("Rejected passes:")
            for p in self.rejected_passes:
                lines.append(f"  ✗ {p.name} (cost={p.cost:.2f}, benefit={p.benefit:.2f})")

        return "\n".join(lines)


class KnapsackSelector:
    """
    Selects the optimal subset of optimization passes using
    the 0/1 Knapsack algorithm (dynamic programming).

    Given a set of available passes, each with a cost (risk) and
    benefit (improvement), this selector finds the subset that
    maximizes total benefit while keeping total cost within budget.

    Algorithm: Dynamic programming O(n·W) where:
    - n = number of available passes
    - W = budget (discretized into integer units)
    """

    def __init__(self, budget: float = 0.6, precision: int = 100) -> None:
        """
        Initialize the knapsack selector.

        Args:
            budget: Maximum total risk budget (0.0 to 1.0).
            precision: Discretization precision (higher = more precise but slower).
        """
        self.budget = budget
        self.precision = precision

    def select(
        self,
        passes: list[PassInfo],
        metrics: dict | None = None,
    ) -> KnapsackResult:
        """
        Select the optimal subset of passes.

        Args:
            passes: List of available optimization passes.
            metrics: Optional current metrics (for future context-aware selection).

        Returns:
            KnapsackResult with the selected passes and summary.
        """
        if not passes:
            return KnapsackResult(
                selected_passes=[],
                total_cost=0.0,
                total_benefit=0.0,
                budget=self.budget,
                all_passes=[],
            )

        # Filter out passes with zero benefit
        viable = [p for p in passes if p.benefit > 0]
        if not viable:
            return KnapsackResult(
                selected_passes=[],
                total_cost=0.0,
                total_benefit=0.0,
                budget=self.budget,
                all_passes=passes,
            )

        # Resolve prerequisites — ensure required passes are included
        viable = self._resolve_prerequisites(viable, passes)

        # Discretize costs and budget
        W = int(self.budget * self.precision)
        n = len(viable)

        weights = [max(1, int(p.cost * self.precision)) for p in viable]
        values = [int(p.benefit * self.precision) for p in viable]

        # DP table
        dp = [[0] * (W + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            for w in range(W + 1):
                dp[i][w] = dp[i - 1][w]
                if weights[i - 1] <= w:
                    val = dp[i - 1][w - weights[i - 1]] + values[i - 1]
                    if val > dp[i][w]:
                        dp[i][w] = val

        # Backtrack to find selected items
        selected = []
        w = W
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.append(viable[i - 1])
                w -= weights[i - 1]

        selected.reverse()

        # Force-include prerequisites of selected passes
        selected = self._ensure_prerequisites(selected, viable)

        total_cost = sum(p.cost for p in selected)
        total_benefit = sum(p.benefit for p in selected)

        return KnapsackResult(
            selected_passes=selected,
            total_cost=total_cost,
            total_benefit=total_benefit,
            budget=self.budget,
            all_passes=passes,
        )

    def _resolve_prerequisites(
        self, viable: list[PassInfo], all_passes: list[PassInfo]
    ) -> list[PassInfo]:
        """
        Ensure prerequisites are included in the viable set.

        If a pass requires another pass to run first, include the
        prerequisite in the viable set (even if it has zero benefit).
        """
        all_by_name = {p.name: p for p in all_passes}
        result_names = {p.name for p in viable}
        result = list(viable)

        changed = True
        while changed:
            changed = False
            for p in list(result):
                for prereq_name in p.prerequisites:
                    if prereq_name not in result_names and prereq_name in all_by_name:
                        result.append(all_by_name[prereq_name])
                        result_names.add(prereq_name)
                        changed = True

        return result

    def _ensure_prerequisites(
        self, selected: list[PassInfo], all_viable: list[PassInfo]
    ) -> list[PassInfo]:
        """
        Force-include prerequisite passes for any selected passes.

        After DP selection, a prerequisite with zero benefit won't be
        chosen by the solver. This method adds them back.
        """
        viable_by_name = {p.name: p for p in all_viable}
        selected_names = {p.name for p in selected}
        result = list(selected)

        changed = True
        while changed:
            changed = False
            for p in list(result):
                for prereq_name in p.prerequisites:
                    if prereq_name not in selected_names and prereq_name in viable_by_name:
                        result.insert(0, viable_by_name[prereq_name])  # Prerequisites first
                        selected_names.add(prereq_name)
                        changed = True

        return result
