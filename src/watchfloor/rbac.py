from __future__ import annotations

from watchfloor.models import User

# Fixture users for the Northbridge Logistics demo. These are invented people.
USERS: dict[str, User] = {
    "ops-lead": User(
        id="ops-lead",
        name="Sam Patel",
        role="site_ops",
        compartments=frozenset({"ops", "shared"}),
        can_reveal_pii=False,
        can_approve=False,
    ),
    "finance": User(
        id="finance",
        name="Riley Chen",
        role="finance",
        compartments=frozenset({"finance", "shared"}),
        can_reveal_pii=True,
        can_approve=False,
    ),
    "approver": User(
        id="approver",
        name="Jordan Lee",
        role="approver",
        compartments=frozenset({"shared"}),
        can_reveal_pii=False,
        can_approve=True,
    ),
}

KNOWN_COMPARTMENTS = frozenset({"ops", "finance", "shared"})


def get_user(user_id: str) -> User:
    try:
        return USERS[user_id]
    except KeyError as exc:
        known = ", ".join(sorted(USERS))
        raise KeyError(f"unknown user '{user_id}'; expected one of: {known}") from exc


def can_access(user: User, compartment: str) -> bool:
    return compartment in user.compartments
