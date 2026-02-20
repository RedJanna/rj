from __future__ import annotations


ADMIN_PHONE = "905304498453"

AUTHORIZED_PERSONS = {
    "otomasyon_admin": {
        "name": "Ömer Alperen Gönen",
        "role": "Otomasyon Yöneticisi",
        "phone": "905304498453",
        "permissions": ["all"],
    },
    "owner_1": {
        "name": "Mehmet Can Ünsal",
        "role": "Otel Sahibi",
        "phone": "",
        "permissions": ["view", "pause", "blacklist"],
    },
    "owner_2": {
        "name": "Özlem Ünsal",
        "role": "Otel Sahibi",
        "phone": "",
        "permissions": ["view", "pause", "blacklist"],
    },
}

RESTAURANT_STAFF = {
    "manager": {
        "name": "Suat Ergül",
        "role": "Restoran Müdürü",
        "phone": "905012969548",
        "notify": True,
    },
    "waiter_1": {
        "name": "Ali",
        "role": "Garson",
        "phone": "",
        "notify": True,
    },
    "waiter_2": {
        "name": "Abdullah",
        "role": "Garson",
        "phone": "",
        "notify": True,
    },
    "waiter_3": {
        "name": "",
        "role": "Garson",
        "phone": "",
        "notify": False,
    },
}

ALLOWED_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-5.1-nano",
    "gpt-5.1-mini",
    "gpt-5.1",
    "gpt-5.2-nano",
    "gpt-5.2-mini",
    "gpt-5.2",
    "o3-mini",
]

MODEL_CHANGE_INFO_TEMPLATE = {
    "changed_at": None,
    "changed_by": None,
    "previous_model": None,
}
