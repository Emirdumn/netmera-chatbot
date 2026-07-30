"""Teknik destek vaka akışı — slotlar tamamlanınca hedefli RAG araması
yapılır, çözülemezse dolu vaka notuyla teknik departmana devredilir."""
from flows.base import Flow, Slot

TECHNICAL_CASE_SLOTS = [
    Slot("platform", "Hangi platformda çalışıyorsunuz (iOS/Android/Web/Flutter/React Native)?",
         "Which platform are you using (iOS/Android/Web/Flutter/React Native)?"),
    Slot("sdk_version", "Hangi SDK sürümünü kullanıyorsunuz?",
         "Which SDK version are you using?"),
    Slot("error_message", "Aldığınız hata mesajı/semptom tam olarak nedir?",
         "What is the exact error message/symptom you're seeing?"),
    Slot("steps_tried", "Şu ana kadar hangi adımları denediniz?",
         "What steps have you already tried?", required=False),
]

technical_case_flow = Flow(name="technical_case", slots=TECHNICAL_CASE_SLOTS)
