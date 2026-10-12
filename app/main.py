"""
US-25 / TASK 1 - Simulated reviews REST API (F5)

Expone vía FastAPI el catálogo de reseñas generado en reviews_data.py.
Cumple con lo pedido en la sección 5 del enunciado para F5:
  "API simulada REST paginada: calificación, texto, fecha, hotel,
   plataforma" con volumen de referencia ~300 reseñas/día.

Endpoints:
  GET /reviews                -> lista paginada, con filtros opcionales
  GET /reviews/{review_id}    -> una reseña puntual
  GET /hotels/{hotel_id}/reviews -> reseñas de un hotel (conveniencia)
  GET /health                 -> healthcheck simple

Ejecutar localmente:
  uvicorn app.main:app --reload --port 8001

Luego, por ejemplo:
  curl "http://localhost:8001/reviews?page=1&page_size=10&language=es"
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

try:
    from .reviews_data import Review, generate_reviews, PLATFORMS, LANGUAGES
except ImportError:
    # Permite correr tanto con "uvicorn app.main:app" (import relativo,
    # paquete) como con "fastapi dev app/main.py" (import absoluto, script).
    from reviews_data import Review, generate_reviews, PLATFORMS, LANGUAGES

app = FastAPI(
    title="HospedaPlus - Simulated Reviews API (F5)",
    description="API simulada de reseñas de huéspedes, para alimentar RN-10 "
                 "(calificación reputacional) y RF-08 (consolidar reseñas).",
    version="1.0.0",
)

# Dataset en memoria, generado una sola vez al arrancar el proceso, con
# semilla fija para reproducibilidad (igual criterio que el resto del seed
# del proyecto: misma semilla -> mismos datos).
SEED = 2026
TOTAL_REVIEWS = 900  # ~3 días de volumen de referencia (300/día) para tener variedad al paginar
DUPLICATE_RATE = 0.08

_REVIEWS: list[Review] = generate_reviews(n=TOTAL_REVIEWS, seed=SEED, duplicate_rate=DUPLICATE_RATE)
_REVIEWS_BY_ID = {r.review_id: r for r in _REVIEWS}


class ReviewOut(BaseModel):
    review_id: str
    hotel_id: str
    platform: str
    language: str
    rating: int
    text: str
    review_date: str
    guest_display_name: str
    duplicate_of: Optional[str] = None


class PaginatedReviews(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[ReviewOut]


@app.get("/health")
def health():
    return {"status": "ok", "total_reviews": len(_REVIEWS)}


def _query_reviews(
    page: int,
    page_size: int,
    hotel_id: Optional[str] = None,
    platform: Optional[str] = None,
    language: Optional[str] = None,
    only_duplicates: bool = False,
) -> PaginatedReviews:
    """
    Lógica de filtrado/paginación pura (sin decoradores de FastAPI), para
    que pueda ser llamada tanto desde /reviews como desde el atajo
    /hotels/{hotel_id}/reviews sin arrastrar objetos Query() sin resolver.
    """
    if platform and platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform debe ser una de: {PLATFORMS}")
    if language and language not in LANGUAGES:
        raise HTTPException(status_code=400, detail=f"language debe ser una de: {LANGUAGES}")

    filtered = _REVIEWS
    if hotel_id:
        filtered = [r for r in filtered if r.hotel_id == hotel_id]
    if platform:
        filtered = [r for r in filtered if r.platform == platform]
    if language:
        filtered = [r for r in filtered if r.language == language]
    if only_duplicates:
        filtered = [r for r in filtered if r.duplicate_of is not None]

    total_items = len(filtered)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    return PaginatedReviews(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=[ReviewOut(**r.__dict__) for r in page_items],
    )


@app.get("/reviews", response_model=PaginatedReviews)
def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    hotel_id: Optional[str] = Query(None, description="Filtrar por hotel, p.ej. hotel-001"),
    platform: Optional[str] = Query(None, description=f"Una de: {', '.join(PLATFORMS)}"),
    language: Optional[str] = Query(None, description=f"Una de: {', '.join(LANGUAGES)}"),
    only_duplicates: bool = Query(False, description="Si es true, devuelve solo las reseñas marcadas como duplicadas de otra"),
):
    """
    Lista reseñas de forma paginada. Soporta filtros simples por hotel,
    plataforma e idioma, y un flag para aislar fácilmente los casos
    duplicados entre plataformas (útil para probar AC1 sin tener que
    escanear las 900 reseñas a mano).
    """
    return _query_reviews(
        page=page, page_size=page_size, hotel_id=hotel_id,
        platform=platform, language=language, only_duplicates=only_duplicates,
    )


@app.get("/reviews/{review_id}", response_model=ReviewOut)
def get_review(review_id: str):
    """Atajo de conveniencia equivalente a /reviews?review_id=...  Ejemplo: rev-000123"""
    review = _REVIEWS_BY_ID.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewOut(**review.__dict__)


@app.get("/hotels/{hotel_id}/reviews", response_model=PaginatedReviews)
def list_reviews_by_hotel(
    hotel_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Atajo de conveniencia equivalente a /reviews?hotel_id=...  Ejemplo: hotel-001"""
    return _query_reviews(page=page, page_size=page_size, hotel_id=hotel_id)