"""
The plan types a report is grouped by.

A person asks about their 401(k), not about a "defined contribution plan with
characteristics code 2J". These are the buckets they would name, mapped onto
the characteristics codes the employer actually filed.

One plan can carry several codes, so two orders are needed and they are not the
same. `precedence` decides which heading a plan lands under: the most specific
signal wins, so a plan whose own name says 457(b) is a 457(b) even though it
also filed code 2J, because 457 plans have no characteristics code of their own
and 2J is filed loosely. The tuple order is what the reader sees, which follows
how people ask: 401(k) first.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import PlanCategory, PlanFeature


@dataclass(frozen=True, slots=True)
class PlanType:
    """One heading in the report, and what puts a plan under it."""

    key: str
    label: str

    features: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    #: Lower wins when a plan matches more than one type.
    precedence: int = 50

    def matches(self, features: set[str], category: str | None) -> bool:
        if features & set(self.features):
            return True

        return bool(self.categories) and category in self.categories


PLAN_TYPES: tuple[PlanType, ...] = (
    PlanType(
        "401k",
        "401(k)",
        features=(PlanFeature.K401,),
        aliases=("401(k)", "401", "k401"),
        precedence=30,
    ),
    PlanType(
        "403b",
        "403(b)",
        features=(PlanFeature.B403,),
        aliases=("403(b)", "403", "b403"),
        precedence=20,
    ),
    PlanType(
        "457b",
        "457(b)",
        features=(PlanFeature.B457,),
        aliases=("457(b)", "457", "b457"),
        precedence=10,
    ),
    PlanType(
        "esop",
        "ESOP",
        features=(PlanFeature.ESOP, PlanFeature.STOCK_BONUS),
        aliases=("employee stock ownership", "stock bonus"),
        precedence=40,
    ),
    PlanType(
        "profit-sharing",
        "Profit Sharing",
        features=(PlanFeature.PROFIT_SHARING,),
        aliases=("profit sharing", "profitsharing"),
        precedence=60,
    ),
    PlanType(
        "money-purchase",
        "Money Purchase",
        features=(PlanFeature.MONEY_PURCHASE, PlanFeature.TARGET_BENEFIT),
        aliases=("money purchase", "target benefit"),
        precedence=65,
    ),
    PlanType(
        "cash-balance",
        "Cash Balance",
        features=(PlanFeature.CASH_BALANCE,),
        aliases=("cash balance",),
        precedence=45,
    ),
    PlanType(
        "pension",
        "Pension / Defined Benefit",
        features=(PlanFeature.PENSION_DB,),
        categories=(PlanCategory.DEFINED_BENEFIT,),
        aliases=("pension", "defined benefit", "db"),
        precedence=70,
    ),
    PlanType(
        "sep-simple",
        "SEP / SIMPLE",
        features=(PlanFeature.SEP_SIMPLE_408,),
        aliases=("sep", "simple", "408"),
        precedence=48,
    ),
    PlanType(
        "other-dc",
        "Other Defined Contribution",
        categories=(PlanCategory.DEFINED_CONTRIBUTION, PlanCategory.BOTH),
        aliases=("other", "defined contribution", "dc"),
        precedence=90,
    ),
)

OTHER = PlanType("other", "Other", precedence=99)

_BY_KEY = {plan_type.key: plan_type for plan_type in PLAN_TYPES}


def resolve_plan_type(text: str | None) -> PlanType | None:
    """Look a type up the way a person would type it, or None for all types."""

    wanted = (text or "").strip().lower()
    if not wanted:
        return None

    if wanted in _BY_KEY:
        return _BY_KEY[wanted]

    squashed = wanted.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")

    for plan_type in PLAN_TYPES:
        candidates = {plan_type.key, plan_type.label.lower(), *plan_type.aliases}
        for candidate in candidates:
            trimmed = candidate.lower().replace("(", "").replace(")", "")
            if squashed == trimmed.replace("-", "").replace(" ", "").replace("/", ""):
                return plan_type

    return None


def classify_plan(features: tuple[str, ...] | str | None, category: str | None) -> PlanType:
    """Which heading one plan belongs under."""

    if isinstance(features, str):
        parsed = {item for item in features.split("|") if item}
    else:
        parsed = {str(item) for item in (features or ())}

    candidates = [
        plan_type for plan_type in PLAN_TYPES if plan_type.matches(parsed, category)
    ]

    if not candidates:
        return OTHER

    return min(candidates, key=lambda plan_type: plan_type.precedence)


def type_keys() -> tuple[str, ...]:
    return tuple(plan_type.key for plan_type in PLAN_TYPES)
