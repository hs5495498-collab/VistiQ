"""
Diversity-aware reranking — Phase 3.

A simple, deterministic form of Maximal Marginal Relevance (MMR): starting
from the already-score-sorted candidate list, greedily picks the next
outfit that best balances its own score against how much it OVERLAPS
(shares items with) outfits already selected — using Jaccard similarity
over item-ID sets as the overlap measure.

Why Jaccard-over-item-IDs, and why plain greedy MMR, rather than something
heavier: VISTIQ's "items" are discrete database rows, not continuous
feature vectors — Jaccard similarity on item-ID sets IS the exact, natural
overlap measure here, not an approximation standing in for a "real" one.
Candidate sets are capped in the hundreds (MAX_COMBOS_PER_TEMPLATE in
engine.py), not millions — a heavier diversity algorithm would add
complexity with no corresponding benefit at this scale.

Trade-off (relevance vs. diversity), stated plainly: this only ever
chooses AMONG the pre-scored, already-ranked candidates. It can change
which of several HIGH-scoring outfits get returned, and in what order, but
it can never promote a low-scoring outfit purely for being different from
the rest — rank #1 is always the single best-scored candidate in the
search window, full stop. "Outfit quality" always wins; "different from
what's already shown" only ever breaks ties among outfits that are already
close in quality. This is deliberately conservative, per the project
requirement to never sacrifice compatibility just to maximize diversity.
"""

from typing import Callable, TypeVar

T = TypeVar("T")

# How much a candidate's overlap with already-selected outfits discounts
# its effective rank. 0.0 would disable diversity entirely; 1.0 would let
# a fully-overlapping candidate's effective value hit zero.
DIVERSITY_LAMBDA = 0.35

# Diversity selection only searches within this many candidates (a
# multiple of top_k, floored at MIN_RERANK_WINDOW) — bounds the O(window *
# top_k) cost and, just as importantly, keeps diversity from reaching deep
# into low-quality territory just to find something "different."
RERANK_WINDOW_MULTIPLIER = 10
MIN_RERANK_WINDOW = 30


def _jaccard(a: frozenset, b: frozenset) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def select_diverse(
    scored_candidates: list[T],
    top_k: int,
    score_of: Callable[[T], float],
    item_ids_of: Callable[[T], frozenset[int]],
) -> list[T]:
    """`scored_candidates` must already be sorted best-first with a
    deterministic tiebreak (exactly as engine.py produces) — this function
    adds no randomness and breaks its own ties by that same original
    order, so the result is fully deterministic for identical input.

    `score_of` / `item_ids_of` extract what's needed from one candidate,
    so this module stays agnostic of engine.py's exact candidate shape.
    """
    if top_k <= 0 or not scored_candidates:
        return []

    window_size = max(MIN_RERANK_WINDOW, top_k * RERANK_WINDOW_MULTIPLIER)
    window = scored_candidates[:window_size]

    selected: list[T] = [window[0]]
    selected_ids: list[frozenset[int]] = [item_ids_of(window[0])]
    remaining = window[1:]

    while remaining and len(selected) < top_k:
        best_index = 0
        best_value = None
        for index, candidate in enumerate(remaining):
            raw_score = score_of(candidate)
            candidate_ids = item_ids_of(candidate)
            max_overlap = max((_jaccard(candidate_ids, chosen) for chosen in selected_ids), default=0.0)
            mmr_value = raw_score - DIVERSITY_LAMBDA * max_overlap * raw_score
            # Strict `>` only — ties keep the earliest candidate in
            # `remaining`, which is itself already in deterministic
            # score-then-id order from engine.py. This is what makes the
            # whole selection deterministic.
            if best_value is None or mmr_value > best_value:
                best_value = mmr_value
                best_index = index
        chosen = remaining.pop(best_index)
        selected.append(chosen)
        selected_ids.append(item_ids_of(chosen))

    return selected
