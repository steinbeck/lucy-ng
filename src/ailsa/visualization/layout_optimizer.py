"""Constraint-based layout optimization for NMR correlation diagrams.

This module provides a holistic optimization system that positions all SVG elements
(atom numbers, arrows, legend) without overlaps while maintaining visual clarity
and proximity to their associated atoms.

The optimizer uses scipy's basin-hopping algorithm with L-BFGS-B local minimizer
to handle the non-convex optimization problem.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import basinhopping, minimize

from .models import (
    ArrowElement,
    AtomNumberElement,
    BoundingBox,
    ElementType,
    LayoutElement,
    LayoutProblem,
    LayoutSolution,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray


# =============================================================================
# Custom Step-Taker for Basin-Hopping
# =============================================================================


class DirectionFlippingStep:
    """Custom step-taker that can flip arrow direction variables.

    For most variables, uses normal random displacement.
    For direction variables (bounded -1 to 1), occasionally flips them completely.
    """

    def __init__(
        self,
        var_info: list[dict],
        bounds: list[tuple[float, float]],
        step_size: float = 0.5,
        flip_probability: float = 0.3,
        rng: np.random.Generator | None = None,
    ):
        """Initialize the step-taker.

        Args:
            var_info: List of variable info dicts (type, index, var name)
            bounds: List of (min, max) bounds for each variable
            step_size: Normal step size for continuous variables
            flip_probability: Probability of flipping direction variables
            rng: Random number generator
        """
        self.var_info = var_info
        self.bounds = bounds
        self.step_size = step_size
        self.flip_probability = flip_probability
        self.rng = rng if rng is not None else np.random.default_rng()

        # Identify which variables are direction variables
        self.direction_indices = [
            i
            for i, info in enumerate(var_info)
            if info.get("type") == "arrow" and info.get("var") == "direction"
        ]

    def __call__(self, x: NDArray) -> NDArray:
        """Take a random step from current position.

        Args:
            x: Current variable values

        Returns:
            New variable values after step
        """
        x_new = x.copy()

        for i in range(len(x)):
            if i in self.direction_indices:
                # Direction variable: either flip or small step
                if self.rng.random() < self.flip_probability:
                    # Flip the direction completely
                    x_new[i] = -x[i]
                else:
                    # Small step
                    x_new[i] = x[i] + self.rng.uniform(-0.3, 0.3)
            else:
                # Regular variable: random displacement
                x_new[i] = x[i] + self.rng.uniform(-self.step_size, self.step_size)

            # Clip to bounds
            lo, hi = self.bounds[i]
            x_new[i] = np.clip(x_new[i], lo, hi)

        return x_new


# =============================================================================
# Geometry Utilities
# =============================================================================


def point_to_segment_distance(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    """Compute minimum distance from point to line segment.

    Args:
        point: The point (x, y)
        seg_start: Start of segment (x, y)
        seg_end: End of segment (x, y)

    Returns:
        Minimum distance from point to segment
    """
    px, py = point
    x1, y1 = seg_start
    x2, y2 = seg_end

    dx = x2 - x1
    dy = y2 - y1

    # Handle degenerate segment (point)
    seg_length_sq = dx * dx + dy * dy
    if seg_length_sq < 1e-10:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

    # Project point onto line, clamping to segment
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / seg_length_sq))

    # Nearest point on segment
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    return math.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)


def segment_to_segment_distance(
    seg1_start: tuple[float, float],
    seg1_end: tuple[float, float],
    seg2_start: tuple[float, float],
    seg2_end: tuple[float, float],
) -> float:
    """Compute minimum distance between two line segments.

    Args:
        seg1_start, seg1_end: First segment endpoints
        seg2_start, seg2_end: Second segment endpoints

    Returns:
        Minimum distance between segments
    """
    # Check all four point-to-segment distances and take minimum
    d1 = point_to_segment_distance(seg1_start, seg2_start, seg2_end)
    d2 = point_to_segment_distance(seg1_end, seg2_start, seg2_end)
    d3 = point_to_segment_distance(seg2_start, seg1_start, seg1_end)
    d4 = point_to_segment_distance(seg2_end, seg1_start, seg1_end)

    return min(d1, d2, d3, d4)


def curve_intersects_box(
    sampled_points: list[tuple[float, float]],
    bbox: BoundingBox,
    stroke_width: float = 2.0,
) -> float:
    """Check if a sampled curve intersects a bounding box.

    Returns the approximate "intrusion" distance if intersecting, 0 otherwise.
    """
    total_intrusion = 0.0
    half_stroke = stroke_width / 2

    for point in sampled_points:
        px, py = point

        # Check if point is inside expanded bbox
        if (
            bbox.x_min - half_stroke <= px <= bbox.x_max + half_stroke
            and bbox.y_min - half_stroke <= py <= bbox.y_max + half_stroke
        ):
            # Calculate intrusion depth
            dx_left = px - (bbox.x_min - half_stroke)
            dx_right = (bbox.x_max + half_stroke) - px
            dy_top = py - (bbox.y_min - half_stroke)
            dy_bottom = (bbox.y_max + half_stroke) - py

            # Minimum intrusion from any edge
            intrusion = min(dx_left, dx_right, dy_top, dy_bottom)
            if intrusion > 0:
                total_intrusion += intrusion

    return total_intrusion


# =============================================================================
# Layout Optimizer
# =============================================================================


@dataclass
class OptimizationConfig:
    """Configuration for the layout optimizer."""

    # Cost function weights
    overlap_weight: float = 1000.0  # Hard constraint (primary)
    distance_weight: float = 10.0  # Keep labels near atoms (secondary)
    aesthetic_weight: float = 1.0  # Prefer consistent positions (tertiary)
    canvas_boundary_weight: float = 500.0  # Penalty for going out of bounds

    # Optimization parameters
    max_time_seconds: float = 8.0
    basin_hopping_iterations: int = 30
    local_max_iterations: int = 100
    temperature: float = 1.0

    # Fallback thresholds (for multi-tier relaxation)
    tier1_time: float = 6.0  # Strict constraints
    tier2_time: float = 8.0  # Relaxed constraints


class LayoutOptimizer:
    """Constraint-based layout optimizer using basin-hopping.

    Optimizes positions of atom number labels and arrow curvatures
    to minimize overlaps while maintaining visual clarity.

    Algorithm:
    1. Pack all movable variables into a flat vector
    2. Use basin-hopping with L-BFGS-B to find global minimum
    3. Cost function penalizes: overlaps, excessive distances, aesthetics
    4. Multi-tier fallback if optimization struggles
    """

    def __init__(self, config: OptimizationConfig | None = None) -> None:
        """Initialize optimizer with configuration.

        Args:
            config: Optimization configuration (uses defaults if not provided)
        """
        self.config = config or OptimizationConfig()
        self._problem: LayoutProblem | None = None
        self._var_info: list[dict] | None = None

    def optimize(
        self,
        problem: LayoutProblem,
        max_time_seconds: float | None = None,
    ) -> LayoutSolution:
        """Optimize layout to minimize overlaps.

        Args:
            problem: The layout problem with fixed and movable elements
            max_time_seconds: Override for max optimization time

        Returns:
            LayoutSolution with optimized positions
        """
        start_time = time.time()
        max_time = max_time_seconds or self.config.max_time_seconds
        warnings: list[str] = []

        self._problem = problem

        # Pack variables and bounds
        x0, bounds, var_info = self._pack_variables(problem)
        self._var_info = var_info

        if len(x0) == 0:
            # No movable elements
            return LayoutSolution(
                atom_numbers=problem.atom_numbers,
                arrows=problem.arrows,
                total_cost=0.0,
                overlap_area=0.0,
                overlap_count=0,
                warnings=[],
                optimization_time_ms=0.0,
            )

        # Define cost function for scipy
        def cost_func(x: NDArray) -> float:
            return self._compute_cost(x, problem, var_info)

        # Create custom step-taker that can flip arrow directions
        rng = np.random.default_rng(42)  # Reproducibility
        step_taker = DirectionFlippingStep(
            var_info=var_info,
            bounds=bounds,
            step_size=0.5,
            flip_probability=0.3,  # 30% chance to flip each direction
            rng=rng,
        )

        # Tier 1: Strict optimization with basin-hopping
        best_result = None
        try:
            result = basinhopping(
                cost_func,
                x0,
                minimizer_kwargs={
                    "method": "L-BFGS-B",
                    "bounds": bounds,
                    "options": {"maxiter": self.config.local_max_iterations},
                },
                niter=self.config.basin_hopping_iterations,
                T=self.config.temperature,
                take_step=step_taker,  # Use custom step-taker
                seed=42,  # Reproducibility
            )
            best_result = result.x
            best_cost = result.fun
        except Exception as e:
            warnings.append(f"Basin-hopping failed: {e}")
            # Fall back to simple L-BFGS-B
            try:
                result = minimize(
                    cost_func,
                    x0,
                    method="L-BFGS-B",
                    bounds=bounds,
                    options={"maxiter": 200},
                )
                best_result = result.x
                best_cost = result.fun
            except Exception as e2:
                warnings.append(f"L-BFGS-B also failed: {e2}")
                best_result = x0
                best_cost = cost_func(x0)

        # Check time and possibly do tier 2 with relaxed constraints
        elapsed = time.time() - start_time
        if elapsed < max_time and best_cost > 100:
            # Tier 2: Try with relaxed distance constraints
            relaxed_problem = LayoutProblem(
                fixed_elements=problem.fixed_elements,
                atom_numbers=problem.atom_numbers,
                arrows=problem.arrows,
                canvas_width=problem.canvas_width,
                canvas_height=problem.canvas_height,
                max_label_distance=30.0,  # Relaxed from 25
                min_label_distance=8.0,  # Relaxed from 10
                min_curvature=1.0,  # Relaxed from 1.2
                max_curvature=3.0,  # Relaxed from 2.5
            )
            x0_relaxed, bounds_relaxed, var_info_relaxed = self._pack_variables(
                relaxed_problem
            )

            def cost_func_relaxed(x: NDArray) -> float:
                return self._compute_cost(x, relaxed_problem, var_info_relaxed)

            try:
                result2 = minimize(
                    cost_func_relaxed,
                    best_result,
                    method="L-BFGS-B",
                    bounds=bounds_relaxed,
                    options={"maxiter": 100},
                )
                if result2.fun < best_cost:
                    best_result = result2.x
                    best_cost = result2.fun
                    warnings.append("Used relaxed constraints for better result")
            except Exception:
                pass  # Keep previous result

        # Apply optimized variables to elements
        self._unpack_variables(best_result, problem, var_info)

        # Calculate final overlap statistics
        overlap_area, overlap_count = self._calculate_overlap_stats(problem)

        if overlap_count > 0:
            warnings.append(f"Minor overlaps remain ({overlap_count} areas)")

        elapsed_ms = (time.time() - start_time) * 1000

        return LayoutSolution(
            atom_numbers=problem.atom_numbers,
            arrows=problem.arrows,
            total_cost=best_cost,
            overlap_area=overlap_area,
            overlap_count=overlap_count,
            warnings=warnings,
            optimization_time_ms=elapsed_ms,
        )

    def _pack_variables(
        self, problem: LayoutProblem
    ) -> tuple[NDArray, list[tuple[float, float]], list[dict]]:
        """Pack all movable element variables into a flat array.

        For each atom number: [angle, distance]
        For each arrow: [curvature, direction]

        Returns:
            Tuple of (initial values, bounds, variable info)
        """
        variables: list[float] = []
        bounds: list[tuple[float, float]] = []
        var_info: list[dict] = []

        # Pack atom number variables
        for i, atom_num in enumerate(problem.atom_numbers):
            # Angle: [0, 2*pi]
            variables.append(atom_num.offset_angle)
            bounds.append((0.0, 2 * math.pi))
            var_info.append({"type": "atom_number", "index": i, "var": "angle"})

            # Distance: [min, max]
            variables.append(atom_num.offset_distance)
            bounds.append((problem.min_label_distance, problem.max_label_distance))
            var_info.append({"type": "atom_number", "index": i, "var": "distance"})

        # Pack arrow variables
        for i, arrow in enumerate(problem.arrows):
            # Curvature: [min, max]
            variables.append(arrow.curvature)
            bounds.append((problem.min_curvature, problem.max_curvature))
            var_info.append({"type": "arrow", "index": i, "var": "curvature"})

            # Direction: [-1, 1] (interpreted via sign)
            variables.append(arrow.direction)
            bounds.append((-1.0, 1.0))
            var_info.append({"type": "arrow", "index": i, "var": "direction"})

        return np.array(variables), bounds, var_info

    def _unpack_variables(
        self,
        x: NDArray,
        problem: LayoutProblem,
        var_info: list[dict],
    ) -> None:
        """Unpack variables and apply to elements.

        Arrow direction: use sign(x[i]) to get +1 or -1
        """
        atom_num_angles: dict[int, float] = {}
        atom_num_distances: dict[int, float] = {}
        arrow_curvatures: dict[int, float] = {}
        arrow_directions: dict[int, float] = {}

        for i, info in enumerate(var_info):
            if info["type"] == "atom_number":
                idx = info["index"]
                if info["var"] == "angle":
                    atom_num_angles[idx] = x[i]
                else:
                    atom_num_distances[idx] = x[i]
            elif info["type"] == "arrow":
                idx = info["index"]
                if info["var"] == "curvature":
                    arrow_curvatures[idx] = x[i]
                else:
                    # Interpret direction via sign
                    arrow_directions[idx] = 1.0 if x[i] >= 0 else -1.0

        # Apply to atom numbers
        for idx, atom_num in enumerate(problem.atom_numbers):
            if idx in atom_num_angles and idx in atom_num_distances:
                atom_num.update_position(atom_num_angles[idx], atom_num_distances[idx])

        # Apply to arrows
        for idx, arrow in enumerate(problem.arrows):
            if idx in arrow_curvatures and idx in arrow_directions:
                arrow.update_curve(arrow_curvatures[idx], arrow_directions[idx])

    def _compute_cost(
        self,
        x: NDArray,
        problem: LayoutProblem,
        var_info: list[dict],
    ) -> float:
        """Compute total cost for a variable configuration.

        Cost = overlap_penalty * 1000 + distance_penalty * 10 + aesthetic_penalty * 1
        """
        # Temporarily apply variables
        self._unpack_variables(x, problem, var_info)

        # Collect all element bounding boxes
        all_elements: list[LayoutElement] = list(problem.fixed_elements)
        all_elements.extend(problem.atom_numbers)
        all_elements.extend(problem.arrows)

        # Calculate overlap penalty
        overlap_penalty = self._calculate_overlap_penalty(all_elements, problem)

        # Calculate distance penalty (labels too far from atoms)
        distance_penalty = self._calculate_distance_penalty(problem.atom_numbers, problem)

        # Calculate aesthetic penalty (prefer consistent label positioning)
        aesthetic_penalty = self._calculate_aesthetic_penalty(problem.atom_numbers)

        # Calculate canvas boundary penalty
        boundary_penalty = self._calculate_boundary_penalty(
            all_elements, problem.canvas_width, problem.canvas_height
        )

        total_cost = (
            overlap_penalty * self.config.overlap_weight
            + distance_penalty * self.config.distance_weight
            + aesthetic_penalty * self.config.aesthetic_weight
            + boundary_penalty * self.config.canvas_boundary_weight
        )

        return total_cost

    def _calculate_overlap_penalty(
        self,
        elements: list[LayoutElement],
        problem: LayoutProblem,
    ) -> float:
        """Calculate penalty for overlapping elements."""
        penalty = 0.0

        # Check pairwise bbox overlaps
        for i, elem_a in enumerate(elements):
            for elem_b in elements[i + 1 :]:
                area = elem_a.bbox.intersection_area(elem_b.bbox)
                if area > 0:
                    penalty += area

        # Additional check: arrow curves vs atom number bboxes
        for arrow in problem.arrows:
            for atom_num in problem.atom_numbers:
                intrusion = curve_intersects_box(
                    arrow.sampled_points, atom_num.bbox, arrow.stroke_width
                )
                penalty += intrusion * 5  # Weight curve intrusions more heavily

        return penalty

    def _calculate_distance_penalty(
        self,
        atom_numbers: list[AtomNumberElement],
        problem: LayoutProblem,
    ) -> float:
        """Calculate penalty for labels too far from their atoms."""
        penalty = 0.0
        ideal_distance = (problem.min_label_distance + problem.max_label_distance) / 2

        for label in atom_numbers:
            # Penalize deviation from ideal distance
            deviation = abs(label.offset_distance - ideal_distance)
            penalty += deviation ** 2

            # Extra penalty if beyond max
            if label.offset_distance > problem.max_label_distance:
                excess = label.offset_distance - problem.max_label_distance
                penalty += excess ** 2 * 10

        return penalty

    def _calculate_aesthetic_penalty(
        self,
        atom_numbers: list[AtomNumberElement],
    ) -> float:
        """Calculate aesthetic penalty for inconsistent positioning.

        Prefers labels on consistent sides (e.g., all bottom-right when possible).
        """
        if len(atom_numbers) < 2:
            return 0.0

        # Calculate angle variance - lower is better (more consistent)
        angles = [an.offset_angle for an in atom_numbers]
        mean_angle = sum(angles) / len(angles)

        # Use circular variance for angles
        variance = 0.0
        for angle in angles:
            diff = angle - mean_angle
            # Normalize to [-pi, pi]
            while diff > math.pi:
                diff -= 2 * math.pi
            while diff < -math.pi:
                diff += 2 * math.pi
            variance += diff ** 2

        return variance / len(angles)

    def _calculate_boundary_penalty(
        self,
        elements: list[LayoutElement],
        canvas_width: int,
        canvas_height: int,
    ) -> float:
        """Calculate penalty for elements outside canvas boundaries."""
        penalty = 0.0
        margin = 10  # Minimum margin from edge

        for elem in elements:
            bbox = elem.bbox

            # Left boundary
            if bbox.x_min < margin:
                penalty += (margin - bbox.x_min) ** 2

            # Right boundary
            if bbox.x_max > canvas_width - margin:
                penalty += (bbox.x_max - (canvas_width - margin)) ** 2

            # Top boundary
            if bbox.y_min < margin:
                penalty += (margin - bbox.y_min) ** 2

            # Bottom boundary
            if bbox.y_max > canvas_height - margin:
                penalty += (bbox.y_max - (canvas_height - margin)) ** 2

        return penalty

    def _calculate_overlap_stats(
        self, problem: LayoutProblem
    ) -> tuple[float, int]:
        """Calculate final overlap statistics."""
        all_elements: list[LayoutElement] = list(problem.fixed_elements)
        all_elements.extend(problem.atom_numbers)
        all_elements.extend(problem.arrows)

        total_area = 0.0
        overlap_count = 0

        for i, elem_a in enumerate(all_elements):
            for elem_b in all_elements[i + 1 :]:
                area = elem_a.bbox.intersection_area(elem_b.bbox)
                if area > 0:
                    total_area += area
                    overlap_count += 1

        return total_area, overlap_count
