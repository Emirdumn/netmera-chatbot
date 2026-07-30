"""Destek vaka akışı — panel kullanımıyla ilgili sorunlarda eksik bağlamı
tamamlamak için sorulacak slotlar."""
from flows.base import Flow, Slot

SUPPORT_CASE_SLOTS = [
    Slot("problem_summary", "Yaşadığınız sorunu kısaca anlatır mısınız?",
         "Could you briefly describe the issue you're facing?"),
    Slot("steps_tried", "Şu ana kadar hangi adımları denediniz?",
         "What steps have you already tried?", required=False),
]

support_case_flow = Flow(name="support_case", slots=SUPPORT_CASE_SLOTS)
