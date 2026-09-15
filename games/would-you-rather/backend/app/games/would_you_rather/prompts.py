from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    option_a: str
    option_b: str


PROMPT_BANK: list[Prompt] = [
    Prompt("Always be 10 minutes late", "Always be 10 minutes early"),
    Prompt("Never use social media again", "Never watch TV or streaming again"),
    Prompt("Be able to fly", "Be invisible"),
    Prompt("Live in the city", "Live in the countryside"),
    Prompt("Have unlimited money but no free time", "Have unlimited free time but no money"),
    Prompt("Always speak your mind", "Never speak again"),
    Prompt("Be famous but hated", "Be unknown but loved"),
    Prompt("Never eat your favorite food again", "Only eat your favorite food forever"),
    Prompt("Know how you die", "Know when you die"),
    Prompt("Travel 100 years to the past", "Travel 100 years to the future"),
    Prompt("Have the ability to read minds", "Have the ability to see the future"),
    Prompt("Only be able to whisper", "Only be able to shout"),
    Prompt("Live without music", "Live without movies"),
    Prompt("Be a superhero with a useless power", "Be a villain with an amazing power"),
    Prompt("Never have to sleep", "Never have to eat"),
    Prompt("Always be cold", "Always be hot"),
    Prompt("Speak every language fluently", "Play every instrument perfectly"),
    Prompt("Have a photographic memory", "Be able to forget anything on command"),
    Prompt("Be the funniest person in the room", "Be the smartest person in the room"),
    Prompt("Live in a world with no internet", "Live in a world with no cars"),
    Prompt("Age only physically", "Age only mentally"),
    Prompt("Have 10 true friends", "Have 1000 acquaintances"),
    Prompt("Be able to control fire", "Be able to control water"),
    Prompt("Always know when someone is lying", "Always win arguments"),
    Prompt("Have a rewind button for life", "Have a pause button for life"),
    Prompt("Own a yacht", "Own a private jet"),
    Prompt("Be extremely strong", "Be extremely fast"),
    Prompt("Never be cold again", "Never be hot again"),
    Prompt("Give up coffee forever", "Give up alcohol forever"),
    Prompt("Have a pet dragon", "Have a pet unicorn"),
    Prompt("Be the best player on a losing team", "Be the worst player on a winning team"),
    Prompt("Only eat sweet foods", "Only eat savory foods"),
    Prompt("Live in summer forever", "Live in winter forever"),
    Prompt("Know all history", "Know all future events"),
    Prompt("Have legs that never tire", "Have arms that never tire"),
    Prompt("Be able to breathe underwater", "Be able to survive in space"),
    Prompt("Never experience physical pain", "Never experience emotional pain"),
    Prompt("Live your life forward", "Live your life backward"),
    Prompt("Always have full phone battery", "Always have perfect WiFi"),
    Prompt("Have the body of a 20-year-old forever", "Have the mind of a 20-year-old forever"),
]
