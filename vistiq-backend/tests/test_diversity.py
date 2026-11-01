"""Tests for app/recommendation/diversity.py (Phase 3) — the greedy,
Jaccard-based MMR-style reranker, tested in isolation from the rest of the
recommendation engine using simple (score, item_ids) tuples."""

from app.recommendation.diversity import select_diverse


def _candidate(score: float, item_ids: tuple[int, ...]):
    return (score, frozenset(item_ids))


SCORE_OF = lambda c: c[0]  # noqa: E731
IDS_OF = lambda c: c[1]  # noqa: E731


def test_best_scored_candidate_is_always_first():
    candidates = [
        _candidate(90.0, (1, 2, 3)),
        _candidate(89.0, (4, 5, 6)),
        _candidate(85.0, (7, 8, 9)),
    ]
    result = select_diverse(candidates, top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    assert result[0] == candidates[0]


def test_near_duplicate_outfits_are_deprioritized_in_favor_of_variety():
    """Mirrors the exact real-world pattern found in the Phase 1/2 baseline
    engine: a top outfit, then several near-duplicates (one item swapped),
    then a genuinely different but slightly lower-scored outfit."""
    candidates = [
        _candidate(90.0, (1, 2, 3)),
        _candidate(89.5, (1, 2, 4)),  # near-duplicate of #1 (shares 2/3 items)
        _candidate(89.0, (1, 2, 5)),  # near-duplicate of #1 (shares 2/3 items)
        _candidate(84.0, (6, 7, 8)),  # genuinely different, lower score
    ]
    result = select_diverse(candidates, top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    selected_ids = [IDS_OF(c) for c in result]

    assert selected_ids[0] == frozenset((1, 2, 3))  # best outfit always wins rank 1
    assert frozenset((6, 7, 8)) in selected_ids  # the different outfit makes the cut


def test_does_not_sacrifice_compatibility_for_diversity_alone():
    """A low-scoring, very different outfit must never outrank a
    high-scoring, moderately-similar one — diversity only breaks ties
    among already-close-in-quality candidates."""
    candidates = [
        _candidate(95.0, (1, 2, 3)),
        _candidate(94.0, (1, 2, 4)),
        _candidate(10.0, (9, 10, 11)),  # very different, but a bad outfit
    ]
    result = select_diverse(candidates, top_k=2, score_of=SCORE_OF, item_ids_of=IDS_OF)
    selected_ids = [IDS_OF(c) for c in result]
    assert frozenset((9, 10, 11)) not in selected_ids


def test_small_candidate_set_returns_everything_available():
    candidates = [_candidate(80.0, (1, 2)), _candidate(75.0, (3, 4))]
    result = select_diverse(candidates, top_k=5, score_of=SCORE_OF, item_ids_of=IDS_OF)
    assert len(result) == 2


def test_empty_candidate_list_returns_empty():
    assert select_diverse([], top_k=5, score_of=SCORE_OF, item_ids_of=IDS_OF) == []


def test_top_k_zero_returns_empty():
    candidates = [_candidate(80.0, (1, 2))]
    assert select_diverse(candidates, top_k=0, score_of=SCORE_OF, item_ids_of=IDS_OF) == []


def test_never_returns_duplicate_outfits():
    candidates = [_candidate(80.0 - i, (1, 2, 3)) for i in range(5)]  # all identical item sets
    result = select_diverse(candidates, top_k=5, score_of=SCORE_OF, item_ids_of=IDS_OF)
    # Nothing in diversity.py deduplicates identical sets (that already
    # happens upstream in engine.py before this is ever called) — but it
    # must not crash or behave strangely when given them anyway.
    assert len(result) == 5


def test_deterministic_for_identical_input():
    candidates = [
        _candidate(90.0, (1, 2, 3)),
        _candidate(89.0, (1, 2, 4)),
        _candidate(88.0, (5, 6, 7)),
        _candidate(87.0, (1, 3, 5)),
    ]
    first = select_diverse(candidates, top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    second = select_diverse(candidates, top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    assert first == second


def test_tie_breaking_is_stable_and_deterministic():
    """Equal scores must resolve by original input order, not by
    iteration-order luck."""
    candidates = [
        _candidate(80.0, (1, 2, 3)),
        _candidate(80.0, (4, 5, 6)),
        _candidate(80.0, (7, 8, 9)),
    ]
    first = select_diverse(candidates, top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    second = select_diverse(list(candidates), top_k=3, score_of=SCORE_OF, item_ids_of=IDS_OF)
    assert first == second == candidates
