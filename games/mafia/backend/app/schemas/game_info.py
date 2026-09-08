from pydantic import BaseModel


class RoleInfoOut(BaseModel):
    key: str
    display_name: str
    team: str
    description: str
    example: str
    acts_at_night: bool
    allow_self_target: bool
    hostile: bool
    max_uses: int | None
    mutually_exclusive_with: list[str]


class PhaseInfoOut(BaseModel):
    key: str
    name: str
    summary: str
    details: str
    example: str


class TieBreakerOptionOut(BaseModel):
    key: str
    label: str
    description: str
    example: str


class TieBreakerInfoOut(BaseModel):
    key: str
    title: str
    description: str
    options: list[TieBreakerOptionOut]


class RuleSectionOut(BaseModel):
    title: str
    body: str
    example: str | None = None


class FaqEntryOut(BaseModel):
    question: str
    answer: str


class GameInfoOut(BaseModel):
    """The full reference-data payload for the Roles / Gameplay /
    Tie-Breakers / Rules / FAQ pages — one endpoint, since it's small and
    entirely static, rather than a round trip per page.
    """

    roles: list[RoleInfoOut]
    phases: list[PhaseInfoOut]
    tie_breakers: list[TieBreakerInfoOut]
    rules: list[RuleSectionOut]
    faq: list[FaqEntryOut]
