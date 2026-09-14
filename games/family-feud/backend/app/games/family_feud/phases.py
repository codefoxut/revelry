from enum import Enum


class FamilyFeudPhase(str, Enum):
    LOBBY = "lobby"
    QUESTION_OPEN = "question_open"
    ANSWERING = "answering"
    STEAL = "steal"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"


FAMILY_FEUD_TRANSITIONS: dict[FamilyFeudPhase, set[FamilyFeudPhase]] = {
    FamilyFeudPhase.LOBBY: {FamilyFeudPhase.QUESTION_OPEN},
    FamilyFeudPhase.QUESTION_OPEN: {FamilyFeudPhase.ANSWERING},
    FamilyFeudPhase.ANSWERING: {FamilyFeudPhase.STEAL, FamilyFeudPhase.ROUND_OVER},
    FamilyFeudPhase.STEAL: {FamilyFeudPhase.ROUND_OVER},
    FamilyFeudPhase.ROUND_OVER: {FamilyFeudPhase.QUESTION_OPEN, FamilyFeudPhase.GAME_OVER},
    FamilyFeudPhase.GAME_OVER: set(),
}
