"""
The VISTIQ recommendation pipeline:

    wardrobe pool -> group by category -> pick outfit templates that fit
    -> generate candidate outfits -> score each with scoring.score_outfit()
    -> rank -> explain -> return the top_k.

This is a rule-based, explainable engine — no ML, no randomness. The same
request against the same database rows always returns the same result.
"""

import itertools

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.models import ClothingItem
from app.recommendation import rules
from app.recommendation.scoring import score_outfit
from app.schemas.recommendation import RecommendationRequest

MAX_COMBOS_PER_TEMPLATE = 200

# Ordered richest -> minimal. "full" templates are preferred whenever the
# wardrobe pool can support them; "partial" templates are only used as a
# fallback when no full outfit can be built.
TEMPLATES = [
    {
        "name": "top_bottom_footwear",
        "required": ["Tops", "Bottoms", "Footwear"],
        "optional": ["Outerwear", "Accessories"],
        "tier": "full",
    },
    {
        "name": "dress_footwear",
        "required": ["Dresses", "Footwear"],
        "optional": ["Outerwear", "Accessories"],
        "tier": "full",
    },
    {
        "name": "top_bottom",
        "required": ["Tops", "Bottoms"],
        "optional": ["Accessories"],
        "tier": "partial",
    },
    {
        "name": "dress_alone",
        "required": ["Dresses"],
        "optional": ["Outerwear", "Accessories"],
        "tier": "partial",
    },
    {
        "name": "top_footwear",
        "required": ["Tops", "Footwear"],
        "optional": ["Accessories"],
        "tier": "partial",
    },
    {
        "name": "bottom_footwear",
        "required": ["Bottoms", "Footwear"],
        "optional": ["Accessories"],
        "tier": "partial",
    },
]

# What a partial template is missing compared to a full outfit — used to
# make the explanation honest about why the outfit is incomplete.
PARTIAL_MISSING_HINTS = {
    "top_bottom": ["Footwear"],
    "dress_alone": ["Footwear"],
    "top_footwear": ["Bottoms"],
    "bottom_footwear": ["Tops"],
}


def _grouped_by_category(items: list[ClothingItem]) -> dict[str, list[ClothingItem]]:
    grouped: dict[str, list[ClothingItem]] = {}
    for item in items:
        category = rules.normalize_category(item.category)
        if category is None:
            continue
        grouped.setdefault(category, []).append(item)
    for category_items in grouped.values():
        category_items.sort(key=lambda i: i.id)
    return grouped


def _select_templates(available_categories: set[str], anchor: ClothingItem | None) -> list[dict]:
    def satisfiable(template: dict) -> bool:
        if not set(template["required"]).issubset(available_categories):
            return False
        if anchor is not None:
            anchor_category = rules.normalize_category(anchor.category)
            all_categories = set(template["required"]) | set(template["optional"])
            if anchor_category not in all_categories:
                return False
        return True

    full = [t for t in TEMPLATES if t["tier"] == "full" and satisfiable(t)]
    if full:
        return full
    return [t for t in TEMPLATES if t["tier"] == "partial" and satisfiable(t)]


def _generate_for_template(
    template: dict,
    grouped: dict[str, list[ClothingItem]],
    anchor: ClothingItem | None,
) -> list[list[ClothingItem]]:
    anchor_category = rules.normalize_category(anchor.category) if anchor else None

    def choices_for(category: str, optional: bool) -> list[ClothingItem | None]:
        if anchor is not None and category == anchor_category:
            # The anchor is mandatory in its own category slot — even if that
            # slot is normally optional, "skip this slot" is not a valid
            # choice once the user has anchored an outfit on this item.
            return [anchor]
        choices: list[ClothingItem | None] = list(grouped.get(category, []))
        if optional:
            choices = [None, *choices]
        return choices

    slots = [(c, False) for c in template["required"]] + [(c, True) for c in template["optional"]]
    choice_lists = [choices_for(category, optional) for category, optional in slots]

    # Every required slot must have at least one candidate item.
    for (category, optional), choices in zip(slots, choice_lists):
        if not optional and not choices:
            return []

    combos = []
    for combo in itertools.islice(itertools.product(*choice_lists), MAX_COMBOS_PER_TEMPLATE):
        combos.append([item for item in combo if item is not None])
    return combos


def _item_summary(item: ClothingItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "color": item.color,
        "style": item.style,
    }


def _generate_explanation(
    items: list[ClothingItem],
    breakdown: dict[str, float],
    request: RecommendationRequest,
    is_partial: bool,
    missing_categories: list[str],
) -> str:
    reasons = []

    if breakdown["color"] >= 0.8:
        colors = ", ".join(sorted({i.color for i in items if i.color}))
        reasons.append(f"the colors ({colors}) complement each other")
    if breakdown["style"] >= 0.8:
        style_label = request.style or (items[0].style if items else "consistent")
        reasons.append(f"the pieces share a consistent {style_label} style")
    if breakdown["occasion"] >= 0.8:
        reasons.append(f"it fits the {request.occasion} occasion")
    if request.weather and breakdown["weather"] >= 0.8:
        reasons.append(f"it suits {request.weather} weather")

    if not reasons:
        reasons.append("it is the most balanced combination available from your selected wardrobe pool")

    explanation = "Recommended because " + " and ".join(reasons) + "."

    if is_partial and missing_categories:
        missing_text = " and ".join(missing_categories)
        explanation += (
            f" Note: no {missing_text} was available in your selected wardrobe pool, "
            "so this is a partial outfit."
        )

    return explanation


def _context(request: RecommendationRequest) -> dict:
    return {
        "occasion": request.occasion,
        "style": request.style,
        "weather": request.weather,
        "selected_item_id": request.selected_item_id,
    }


def build_recommendations(db: Session, request: RecommendationRequest) -> dict:
    """Run the full pipeline and return a dict matching RecommendationResponse."""

    selected_item: ClothingItem | None = None
    candidate_ids = set(request.wardrobe_item_ids)

    if request.selected_item_id is not None:
        selected_item = db.get(ClothingItem, request.selected_item_id)
        if selected_item is None:
            raise HTTPException(
                status_code=404,
                detail=f"Selected item {request.selected_item_id} not found",
            )
        candidate_ids.add(selected_item.id)

    if not candidate_ids:
        return {
            "request": _context(request),
            "recommendations": [],
            "message": "Your selected wardrobe pool is empty, so no outfit recommendations could be generated.",
        }

    candidates = db.query(ClothingItem).filter(ClothingItem.id.in_(candidate_ids)).all()
    if not candidates:
        return {
            "request": _context(request),
            "recommendations": [],
            "message": "None of the supplied wardrobe item ids were found in the database.",
        }

    grouped = _grouped_by_category(candidates)
    available_categories = set(grouped.keys())
    templates = _select_templates(available_categories, selected_item)

    if not templates:
        return {
            "request": _context(request),
            "recommendations": [],
            "message": (
                "Not enough variety in the selected wardrobe pool to build an outfit — "
                "try including items from at least two complementary categories "
                "(e.g. Tops and Bottoms)."
            ),
        }

    # Generate candidate outfits from every satisfiable template, then dedupe
    # by exact item-id set (the same combination can arise from more than
    # one optional-slot choice).
    seen_combinations: set[frozenset[int]] = set()
    unique_combos: list[tuple[dict, list[ClothingItem]]] = []
    for template in templates:
        for items in _generate_for_template(template, grouped, selected_item):
            key = frozenset(item.id for item in items)
            if key in seen_combinations:
                continue
            seen_combinations.add(key)
            unique_combos.append((template, items))

    if not unique_combos:
        return {
            "request": _context(request),
            "recommendations": [],
            "message": "No valid outfit combinations could be built from the selected wardrobe pool.",
        }

    scored = [
        (*score_outfit(items, request.occasion, request.style, request.weather), template, items)
        for template, items in unique_combos
    ]
    # Deterministic ordering: highest score first, then a stable tiebreaker
    # on the outfit's item ids so ties never depend on dict/set iteration order.
    scored.sort(key=lambda s: (-s[0], tuple(sorted(i.id for i in s[3]))))

    top = scored[: request.top_k]

    recommendations = []
    for rank, (final_score, breakdown, template, items) in enumerate(top, start=1):
        is_partial = template["tier"] == "partial"
        missing = PARTIAL_MISSING_HINTS.get(template["name"], []) if is_partial else []
        recommendations.append(
            {
                "rank": rank,
                "score": final_score,
                "items": [_item_summary(i) for i in items],
                "reason": _generate_explanation(items, breakdown, request, is_partial, missing),
            }
        )

    return {
        "request": _context(request),
        "recommendations": recommendations,
        "message": None,
    }
