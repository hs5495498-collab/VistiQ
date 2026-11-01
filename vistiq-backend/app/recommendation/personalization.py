"""
Optional, request-scoped personalization — Phase 3.

No user accounts and no persistent preference storage: every field here
lives only on a single RecommendationRequest and only affects that one
response (see app/schemas/recommendation.py — preferred_colors,
avoided_colors, prefer_favorites, all optional, all defaulted to "no
preference"). There is no architectural need for a preferences table —
preferences are inherently per-request here, not per-user, since VISTIQ
has no accounts (and this phase deliberately does not add any).

Applied as a small, CAPPED additive adjustment to the outfit's existing
0-100 compatibility score (app/recommendation/scoring.py), rather than
folded into that score's weighted-sum formula. Two reasons: it keeps the
original six-dimension compatibility score's meaning completely intact
(directly comparable to the Phase 1/2 baseline, and still the score shown
as "compatibility"), and it makes the personalization effect easy to
explain on its own (e.g. "+4 for including a preferred color") instead of
being invisibly blended into one number.
"""

from app.database.models import ClothingItem
from app.schemas.recommendation import RecommendationRequest

# Caps are deliberately small relative to the 0-100 compatibility score —
# personalization should nudge which otherwise-similar outfits rank
# higher, never override genuine compatibility (e.g. an avoided color on an
# excellent outfit shouldn't out-rank a mediocre one just by avoiding it).
MAX_PREFERRED_COLOR_BONUS = 6.0
MAX_AVOIDED_COLOR_PENALTY = 10.0
MAX_FAVORITE_BONUS = 6.0


def _item_colors(item: ClothingItem) -> set[str]:
    colors = {item.color.strip().lower()} if item.color else set()
    if item.secondary_color:
        colors.add(item.secondary_color.strip().lower())
    return colors


def personalization_adjustment(items: list[ClothingItem], request: RecommendationRequest) -> tuple[float, list[str]]:
    """Returns (point_adjustment, reasons). `point_adjustment` is added
    directly to the outfit's 0-100 score (can be negative). `reasons` are
    plain-language, and only ever describe something that actually
    happened — an empty preference list produces zero adjustment and zero
    reasons, never an invented one.

    Invalid preference values (e.g. a color name that matches nothing in
    the wardrobe, or isn't in VISTIQ's known palette) can never raise or
    misbehave — they simply match zero items, since this only ever checks
    plain case-insensitive string membership. No separate validation is
    needed for that reason.
    """
    adjustment = 0.0
    reasons: list[str] = []

    preferred = {c.strip().lower() for c in request.preferred_colors if c and c.strip()}
    avoided = {c.strip().lower() for c in request.avoided_colors if c and c.strip()}

    if preferred:
        matching_items = [item for item in items if _item_colors(item) & preferred]
        if matching_items:
            bonus = min(MAX_PREFERRED_COLOR_BONUS, 2.0 * len(matching_items))
            adjustment += bonus
            reasons.append(f"includes {len(matching_items)} item(s) in a color you prefer")

    if avoided:
        conflicting_items = [item for item in items if _item_colors(item) & avoided]
        if conflicting_items:
            penalty = min(MAX_AVOIDED_COLOR_PENALTY, 4.0 * len(conflicting_items))
            adjustment -= penalty
            reasons.append(f"includes {len(conflicting_items)} item(s) in a color you asked to avoid")

    if request.prefer_favorites:
        favorite_items = [item for item in items if item.is_favorite]
        if favorite_items:
            bonus = min(MAX_FAVORITE_BONUS, 3.0 * len(favorite_items))
            adjustment += bonus
            reasons.append(f"includes {len(favorite_items)} of your favorite item(s)")

    return adjustment, reasons
