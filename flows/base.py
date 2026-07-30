"""Slot ve Flow modelleri — agent'ların hangi bilgiyi ne zaman soracağını ve
akış tamamlanınca ne yapacağını tanımlar."""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Slot:
    name: str
    question_tr: str
    question_en: str
    required: bool = True

    def question(self, language="tr"):
        return self.question_en if language == "en" else self.question_tr


@dataclass
class Flow:
    name: str
    slots: list
    completion_action: Optional[Callable] = None

    def missing_slots(self, profile, case_notes=None):
        data = {**(profile or {}), **(case_notes or {})}
        missing = []
        for slot in self.slots:
            if not slot.required:
                continue
            value = data.get(slot.name)
            if value is None or value == "" or value == []:
                missing.append(slot)
        return missing

    def is_complete(self, profile, case_notes=None):
        return not self.missing_slots(profile, case_notes)
