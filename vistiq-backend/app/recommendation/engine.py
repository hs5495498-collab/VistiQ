"""
The VISTIQ recommendation pipeline (Phase 3 — hybrid architecture):

    1. Candidate generation   wardrobe pool -> group by category -> pick
                               outfit templates that fit -> generate
                               candidate outfits (unchanged since Phase 1)
    2. Hard constraint filter  a template's required categories must all
                               be present, and the anchor item (if any)
                               must be structurally includable — this IS
                               the hard filter: an outfit that can't
                               satisfy it is never generated at all, not
                               generated-then-rejected
    3. Compatibility scoring  scoring.score_outfit() — six weighted
                               dimensions, color now using real color
                               theory (color_theory.py)
    4. Preference-aware rank  personalization.py's small, capped
                               adjustment (preferred/avoided colors,
                               favorites) added to the compatibility score,
                               then re-sorted
    5. Diversity selection    diversity.py's greedy, Jaccard-based rerank
                               among the top-ranked candidates
    6. Explanation generation _build_explanation() — structured, built
                               only from the evidence scoring.py actually
                               produced, never invented

Each stage is a separate, independently testable function below. This is
a deterministic, rule-based, explainable hybrid engine — no ML, no
randomness anywhere in it — the same request against the same database
rows always returns the same result.
"""

import itertools

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.models import ClothingItem
from app.recommendation import diversity, personalization, rules
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


_NOTABLE_COLOR_TAGS = {
    "classic pairing", "neutral combination", "neutral pairing",
    "monochromatic", "complementary colors", "analogous colors",
}


def _build_explanation(
    items: list[ClothingItem],
    breakdown: dict[str, float],
    evidence: dict,
    request: RecommendationRequest,
    is_partial: bool,
    missing_categories: list[str],
    personalization_reasons: list[str],
) -> tuple[str, list[str], list[str]]:
    """Phase 3 structured explainability. Returns (prose_reason,
    positive_reasons, caveats) — every one of them built only from
    evidence that's actually true for THIS specific outfit (scoring.py's
    `breakdown`/`evidence`, or the request's own personalization result).
    A dimension with no clear signal simply produces no reason for it —
    never a fabricated, generic one."""
    positive_reasons: list[str] = []
    caveats: list[str] = []

    # Color: driven by color_theory.py's actual per-pair relationship tags
    # (evidence["color_tags"]), not just "the average happened to be high"
    # — "colors complement each other" is only ever said when a genuinely
    # classic/neutral/complementary/analogous/monochromatic relationship
    # was actually found for at least one pair in this outfit.
    notable_tags = sorted({tag for tag in evidence.get("color_tags", []) if tag in _NOTABLE_COLOR_TAGS})
    if notable_tags and breakdown["color"] >= 0.75:
        positive_reasons.append(f"Colors work well together ({', '.join(notable_tags)})")

    if breakdown["style"] >= 0.8:
        style_label = request.style or (items[0].style if items else "consistent")
        positive_reasons.append(f"Consistent {style_label} style across the outfit")

    if breakdown["occasion"] >= 0.8:
        positive_reasons.append(f"Matches the {request.occasion} occasion")

    if request.weather and breakdown["weather"] >= 0.8:
        positive_reasons.append(f"Suits {request.weather} weather")

    if breakdown["category"] >= 0.9:
        positive_reasons.append("Good category coverage for a complete outfit")

    if request.selected_item_id is not None:
        anchor_names = [item.name for item in items if item.id == request.selected_item_id]
        if anchor_names:
            positive_reasons.append(f"Includes your anchor item ({anchor_names[0]})")

    positive_reasons.extend(f"Personalization: {reason}" for reason in personalization_reasons)

    if evidence.get("low_color_reliability"):
        caveats.append(
            "One or more items' color was extracted with low reliability — "
            "the color match above may be less certain than it looks."
        )
    if is_partial and missing_categories:
        missing_text = " and ".join(missing_categories)
        caveats.append(f"No {missing_text} was available in your selected wardrobe pool — this is a partial outfit.")
    if breakdown["color"] < 0.55:
        caveats.append("Color compatibility for this combination is uncertain, not confirmed to look bad.")

    if positive_reasons:
        prose = "Recommended because " + "; ".join(reason[0].lower() + reason[1:] for reason in positive_reasons) + "."
    else:
        prose = "Recommended because it is the most balanced combination available from your selected wardrobe pool."
    if caveats:
        prose += " " + " ".join(caveats)

    return prose, positive_reasons, caveats


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
        if selected_item is not None:
            message = (
                f"No valid outfit could include your anchor item ({selected_item.name}, "
                f"{selected_item.category}) together with the rest of your selected wardrobe pool. "
                "Try a different anchor, or include items from a category that pairs with it."
            )
        else:
            message = (
                "Not enough variety in the selected wardrobe pool to build an outfit — "
                "try including items from at least two complementary categories "
                "(e.g. Tops and Bottoms)."
            )
        return {"request": _context(request), "recommendations": [], "message": message}

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

    # --- Stage 3: compatibility scoring -----------------------------------
    # score_outfit() now returns (score, breakdown, evidence) — evidence is
    # what _build_explanation() below uses to avoid inventing reasons.
    scored = [
        (*score_outfit(items, request.occasion, request.style, request.weather), template, items)
        for template, items in unique_combos
    ]

    # --- Stage 4: preference-aware ranking ---------------------------------
    # personalization.py applies a small, capped additive adjustment (can
    # be zero, if the request has no preferences — the default) on top of
    # the raw compatibility score, then everything is re-sorted by the
    # adjusted value. Deterministic ordering: the adjusted score first,
    # then a stable tiebreaker on the outfit's item ids so ties never
    # depend on dict/set iteration order.
    adjusted = []
    for final_score, breakdown, evidence, template, items in scored:
        points, personalization_reasons = personalization.personalization_adjustment(items, request)
        adjusted_score = round(final_score + points, 1)
        adjusted.append((adjusted_score, breakdown, evidence, template, items, personalization_reasons))
    adjusted.sort(key=lambda s: (-s[0], tuple(sorted(i.id for i in s[4]))))

    # --- Stage 5: diversity-aware selection ---------------------------------
    # On by default (request.diversify), opt-out rather than opt-in — see
    # diversity.py for the full relevance-vs-diversity trade-off. Every
    # candidate here already structurally includes the anchor item (if
    # any), so diversity selection can reorder/choose among them but can
    # never remove it.
    if request.diversify:
        selected = diversity.select_diverse(
            adjusted,
            request.top_k,
            score_of=lambda candidate: candidate[0],
            item_ids_of=lambda candidate: frozenset(item.id for item in candidate[4]),
        )
    else:
        selected = adjusted[: request.top_k]

    # --- Stage 6: explanation generation ------------------------------------
    recommendations = []
    for rank, (adjusted_score, breakdown, evidence, template, items, personalization_reasons) in enumerate(
        selected, start=1
    ):
        is_partial = template["tier"] == "partial"
        missing = PARTIAL_MISSING_HINTS.get(template["name"], []) if is_partial else []
        prose, positive_reasons, caveats = _build_explanation(
            items, breakdown, evidence, request, is_partial, missing, personalization_reasons
        )
        recommendations.append(
            {
                "rank": rank,
                "score": max(0.0, min(100.0, adjusted_score)),
                "items": [_item_summary(i) for i in items],
                "reason": prose,
                "dimension_scores": breakdown,
                "positive_reasons": positive_reasons,
                "caveats": caveats,
            }
        )

    return {
        "request": _context(request),
        "recommendations": recommendations,
        "message": None,
    }
