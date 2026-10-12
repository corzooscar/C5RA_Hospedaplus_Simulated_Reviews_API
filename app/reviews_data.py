"""
US-25 / TASK 1 - Datos simulados de reseñas (F5)

Genera reseñas sintéticas en español, inglés y portugués, para los 28
hoteles de la cadena (coherente con F3), incluyendo un subconjunto
deliberadamente DUPLICADO entre plataformas (p.ej. la misma reseña
publicada en Booking.com y TripAdvisor con pequeñas variaciones de texto),
tal como exige el AC1 de HU-25 y la especificación 5.2 del enunciado:
"F5: reseñas en español, inglés y portugués; algunas duplicadas entre
plataformas."

Este módulo solo genera y mantiene los datos en memoria (seedeados de
forma reproducible); main.py expone este catálogo vía API REST paginada.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

HOTEL_IDS = [f"hotel-{i:03d}" for i in range(1, 29)]  # 28 hoteles, igual que en F2/F3
PLATFORMS = ["booking", "tripadvisor", "expedia", "google"]

# Plantillas de reseña por idioma y "sentimiento" (positivo/neutral/negativo),
# para poder generar texto variado sin depender de un servicio externo.
REVIEW_TEMPLATES = {
    "es": {
        "positive": [
            "Excelente estadía, el personal fue muy amable y la habitación impecable.",
            "Muy buena relación calidad-precio, volveríamos sin duda.",
            "La ubicación del hotel es inmejorable, cerca de todo.",
            "El desayuno estuvo delicioso y el check-in fue muy rápido.",
        ],
        "neutral": [
            "La habitación estaba bien, aunque un poco pequeña para el precio.",
            "Todo correcto, sin nada que destacar en especial.",
            "Cumplió con lo esperado, nada extraordinario.",
        ],
        "negative": [
            "El aire acondicionado no funcionaba bien y tardaron en repararlo.",
            "El ruido de la calle no dejaba dormir, poco aislamiento.",
            "La limpieza de la habitación dejó mucho que desear.",
        ],
    },
    "en": {
        "positive": [
            "Fantastic stay, the staff went above and beyond to help us.",
            "Great value for money, the room was spotless and modern.",
            "Perfect location, walking distance to everything we needed.",
            "Breakfast was excellent and check-in was fast and friendly.",
        ],
        "neutral": [
            "The room was fine, a bit small for the price though.",
            "Everything was okay, nothing special to mention.",
            "It met our expectations, nothing more, nothing less.",
        ],
        "negative": [
            "The air conditioning barely worked and it took too long to fix.",
            "Street noise kept us up most nights, poor soundproofing.",
            "Room cleanliness left a lot to be desired.",
        ],
    },
    "pt": {
        "positive": [
            "Estadia excelente, a equipe foi muito atenciosa e o quarto impecável.",
            "Ótimo custo-benefício, com certeza voltaríamos.",
            "Localização imbatível, perto de tudo que precisávamos.",
            "O café da manhã estava delicioso e o check-in foi muito rápido.",
        ],
        "neutral": [
            "O quarto estava bem, um pouco pequeno para o preço.",
            "Tudo certo, nada de especial a destacar.",
            "Atendeu as expectativas, nada mais, nada menos.",
        ],
        "negative": [
            "O ar-condicionado quase não funcionava e demoraram para consertar.",
            "O barulho da rua não deixava dormir, isolamento acústico fraco.",
            "A limpeza do quarto deixou a desejar.",
        ],
    },
}

LANGUAGES = list(REVIEW_TEMPLATES.keys())
SENTIMENTS = ["positive", "neutral", "negative"]
SENTIMENT_WEIGHTS = [0.55, 0.25, 0.20]  # refleja ocupación/reputación promedio razonable
SENTIMENT_RATING_RANGE = {
    "positive": (4, 5),
    "neutral": (3, 3),
    "negative": (1, 2),
}

# Pequeñas variaciones de texto para simular que la MISMA reseña fue
# posteada en dos plataformas distintas (no es idéntica letra por letra,
# como pasaría en la vida real si el huésped la reescribe o la plataforma
# trunca el texto).
DUPLICATE_SUFFIXES = {
    "es": [" (Reseña verificada)", " Repetiría la experiencia.", ""],
    "en": [" (Verified review)", " Would stay again.", ""],
    "pt": [" (Avaliação verificada)", " Ficaríamos novamente.", ""],
}


@dataclass
class Review:
    review_id: str
    hotel_id: str
    platform: str
    language: str
    rating: int
    text: str
    review_date: str  # ISO date
    guest_display_name: str
    duplicate_of: Optional[str] = None  # review_id original si esta es una copia simulada


def _make_guest_name(rng: random.Random) -> str:
    first_names = ["Maria", "Carlos", "Ana", "John", "Laura", "Pedro", "Sofia", "Lucas",
                   "Camila", "Diego", "Julia", "Marco"]
    last_names = ["Garcia", "Silva", "Smith", "Lopez", "Santos", "Martinez", "Ferreira", "Rossi"]
    return f"{rng.choice(first_names)} {rng.choice(last_names)}"


def _random_date(rng: random.Random, days_back: int = 180) -> datetime:
    days = rng.randint(0, days_back)
    return datetime.now(timezone.utc) - timedelta(days=days)


def generate_reviews(n: int, seed: int, duplicate_rate: float = 0.08) -> list[Review]:
    """
    Genera `n` reseñas base y añade duplicados simulados entre plataformas
    para una fracción `duplicate_rate` de ellas. El total devuelto es
    n + round(n * duplicate_rate).
    """
    rng = random.Random(seed)
    reviews: list[Review] = []
    counter = 0

    for _ in range(n):
        counter += 1
        hotel_id = rng.choice(HOTEL_IDS)
        platform = rng.choice(PLATFORMS)
        language = rng.choices(LANGUAGES, weights=[0.5, 0.3, 0.2], k=1)[0]
        sentiment = rng.choices(SENTIMENTS, weights=SENTIMENT_WEIGHTS, k=1)[0]
        rating = rng.randint(*SENTIMENT_RATING_RANGE[sentiment])
        text = rng.choice(REVIEW_TEMPLATES[language][sentiment])
        date = _random_date(rng)
        guest = _make_guest_name(rng)

        review = Review(
            review_id=f"rev-{counter:06d}",
            hotel_id=hotel_id,
            platform=platform,
            language=language,
            rating=rating,
            text=text,
            review_date=date.strftime("%Y-%m-%d"),
            guest_display_name=guest,
        )
        reviews.append(review)

    # --- Duplicados entre plataformas (AC1) ---
    n_duplicates = round(n * duplicate_rate)
    originals_for_dup = rng.sample(reviews, k=min(n_duplicates, len(reviews)))

    for original in originals_for_dup:
        counter += 1
        other_platforms = [p for p in PLATFORMS if p != original.platform]
        dup_platform = rng.choice(other_platforms)
        suffix = rng.choice(DUPLICATE_SUFFIXES[original.language])
        # misma reseña, publicada un par de días después en otra plataforma
        dup_date = datetime.strptime(original.review_date, "%Y-%m-%d") + timedelta(days=rng.randint(1, 5))

        duplicate = Review(
            review_id=f"rev-{counter:06d}",
            hotel_id=original.hotel_id,
            platform=dup_platform,
            language=original.language,
            rating=original.rating,
            text=original.text + suffix,
            review_date=dup_date.strftime("%Y-%m-%d"),
            guest_display_name=original.guest_display_name,
            duplicate_of=original.review_id,
        )
        reviews.append(duplicate)

    # orden estable por fecha, como lo entregaría una API real paginada
    reviews.sort(key=lambda r: r.review_date)
    return reviews
