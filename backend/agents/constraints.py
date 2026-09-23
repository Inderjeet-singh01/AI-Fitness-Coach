import re
from typing import Any, Dict, List, Optional


"""
Turns free-text requirements in the CURRENT user message into explicit,
checkable constraints, so validation never has to judge vague words such as
"cheap" or "Punjabi" by feel:

    diet_type            vegan | vegetarian | eggetarian | None
    cuisine              e.g. "Punjabi" | None      (checked by the judge, as a named check)
    budget               "low" | None
    daily_cost_required  True when budget == "low"  (checked in Python)

Only the current message is used, never earlier turns.
"""


_VEGAN = re.compile(r"\bvegan\b", re.I)
_EGGETARIAN = re.compile(r"\beggetarian\b|\bveg(etarian)?\s*(\+|and|with)\s*eggs?\b", re.I)
_VEGETARIAN = re.compile(r"\b(vegetarian|veggie|pure\s*veg|veg\s+only|only\s+veg|no\s+(meat|non-?veg))\b", re.I)
_LOW_BUDGET = re.compile(
    r"\b(cheap|cheaper|budget|afford|affordable|low[\s-]?cost|inexpensive|economical|"
    r"low\s+income|student\s+budget|not\s+expensive|less\s+money)\b",
    re.I,
)
_CUISINES = [
    "Punjabi", "South Indian", "North Indian", "Gujarati", "Bengali", "Rajasthani", "Maharashtrian",
    "Kerala", "Tamil", "Andhra", "Kashmiri", "Indian", "Pakistani", "Mediterranean", "Chinese",
    "Japanese", "Korean", "Thai", "Mexican", "Italian", "Middle Eastern", "Continental",
]

_MEAT = r"chicken|mutton|lamb|goat|beef|pork|bacon|ham|fish|prawns?|shrimp|crab|seafood|tuna|salmon|meat|keema"
_EGG = r"eggs?|omelette|omelet"
_DAIRY = r"paneer|dahi|curd|yogh?urt|milk|lassi|ghee|butter|cheese|whey|khoa|malai|buttermilk|chaas"
# A line that mentions an item only to exclude or replace it is not a violation.
_NEGATION = re.compile(r"\b(no|avoid|without|instead of|replace|skip|exclude|swap|not)\b", re.I)
_COST_LINE = re.compile(r"estimated\s+daily\s+cost[:\*\s]*~?\s*[^\d\n]{0,6}\s*([\d,]+(?:\.\d+)?)", re.I)


def extract_constraints(query: str) -> Dict[str, Any]:
    text = query or ""
    constraints: Dict[str, Any] = {}

    if _VEGAN.search(text):
        constraints["diet_type"] = "vegan"
    elif _EGGETARIAN.search(text):
        constraints["diet_type"] = "eggetarian"
    elif _VEGETARIAN.search(text):
        constraints["diet_type"] = "vegetarian"

    for cuisine in _CUISINES:
        if re.search(rf"\b{re.escape(cuisine)}\b", text, re.I):
            constraints["cuisine"] = cuisine
            break

    if _LOW_BUDGET.search(text):
        constraints["budget"] = "low"
        constraints["daily_cost_required"] = True

    return constraints


def describe_constraints(constraints: Dict[str, Any]) -> str:
    """Human-readable list for prompts."""
    lines = []
    if constraints.get("diet_type"):
        lines.append(f"- diet_type: {constraints['diet_type']}")
    if constraints.get("cuisine"):
        lines.append(f"- cuisine: {constraints['cuisine']} (meals should be mainly {constraints['cuisine']} dishes)")
    if constraints.get("budget"):
        lines.append(f"- budget: {constraints['budget']} (use inexpensive staple ingredients)")
    if constraints.get("daily_cost_required"):
        lines.append("- daily_cost: must be stated as an estimate")
    return "\n".join(lines) or "None stated."


def forbidden_items(diet_type: Optional[str]) -> Optional[str]:
    if diet_type == "vegan":
        return "|".join((_MEAT, _EGG, _DAIRY))
    if diet_type == "vegetarian":
        return "|".join((_MEAT, _EGG))
    if diet_type == "eggetarian":
        return _MEAT
    return None


def find_diet_violations(diet_plan: str, diet_type: Optional[str]) -> List[str]:
    pattern = forbidden_items(diet_type)
    if not pattern:
        return []
    item_re = re.compile(rf"\b({pattern})\b", re.I)
    found: List[str] = []
    for line in diet_plan.splitlines():
        if _NEGATION.search(line):
            continue
        for match in item_re.finditer(line):
            item = match.group(1).lower()
            if item not in found:
                found.append(item)
    return found


def extract_daily_cost(diet_plan: str) -> Optional[float]:
    match = _COST_LINE.search(diet_plan or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None
