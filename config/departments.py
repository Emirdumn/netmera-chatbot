"""Departman dizini — sunum/demo amaçlı sahte personel kayıtlarıyla."""

DEPARTMENTS = {
    "sales": {
        "name": "Satış",
        "email": "sales@netmera.com",
        "working_hours": "09:00-18:00",
        "staff": [
            {"name": "Ayşe Kaya", "is_online": True},
            {"name": "Mert Yıldız", "is_online": False},
        ],
    },
    "customer_success": {
        "name": "Müşteri Başarı",
        "email": "support@netmera.com",
        "working_hours": "09:00-18:00",
        "staff": [
            {"name": "Elif Demir", "is_online": True},
            {"name": "Can Öztürk", "is_online": False},
        ],
    },
    "engineering": {
        "name": "Teknik Destek / SDK",
        "email": "engineering@netmera.com",
        "working_hours": "09:00-18:00",
        "staff": [
            {"name": "Deniz Arslan", "is_online": False},
            {"name": "Zeynep Şahin", "is_online": True},
        ],
    },
}

# router_agent'ın döndüğü department değerini DEPARTMENTS anahtarına eşler
INTENT_TO_DEPARTMENT = {
    "sales": "sales",
    "support": "customer_success",
    "technical": "engineering",
}
