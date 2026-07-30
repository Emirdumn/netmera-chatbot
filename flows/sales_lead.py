"""Satış lead toplama akışı — slotlar tamamlanınca lead_capture_tool çağrılır."""
from flows.base import Flow, Slot

SALES_LEAD_SLOTS = [
    Slot("person_name", "Öncelikle adınızı öğrenebilir miyim?",
         "Could I have your name, please?"),
    Slot("company", "Hangi şirket için görüşüyoruz?",
         "Which company are you reaching out for?"),
    Slot("email", "Size ulaşabileceğimiz e-posta adresiniz nedir?",
         "What email address can we reach you at?"),
    Slot("app_name", "Uygulamanızın adı/türü nedir?",
         "What is the name/type of your app?"),
    Slot("user_scale", "Tahmini kullanıcı sayınız nedir?",
         "What is your estimated user count?"),
]

sales_lead_flow = Flow(name="sales_lead", slots=SALES_LEAD_SLOTS)
