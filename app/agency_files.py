"""
US-25 / TASK 2 - Generador de archivos de agencias tradicionales (F4)

Genera, por cada agencia (~15, según 5. Fuentes de datos), un archivo CSV
semanal con sus reservas, en formatos ligeramente distintos entre agencias
(columnas con distinto orden/nombre), tal como describe 5.2:
"F4: agencias con formatos distintos y reservas que ya existen por otro
canal (duplicadas entre canales)."

El caso de duplicado (AC2 de HU-25, y RN-08 del enunciado) se construye
tomando una reserva YA EMITIDA por el generador de channel-manager (F2,
HU-24, ver ../../channel_manager_simulator/output/events.jsonl) y creando
una fila de agencia para la MISMA reserva (mismo hotel, mismas fechas,
mismo huésped) pero con:
  - un nombre de huésped con una leve variación (typo/orden de apellidos)
  - un ID de reserva propio de la agencia (no el reservation_id de F2)
  - normalmente una comisión más alta (agencia tradicional, 10%, vs. el
    canal original)

Nota de diseño: el esquema de eventos F2 definido en US-12 no incluye
nombre de huésped (solo adults/children). Para poder simular el defecto
"reserva duplicada entre canales con leves diferencias en el nombre" sin
tocar el contrato ya validado de F2, este generador DERIVA un nombre de
huésped determinístico a partir del reservation_id (misma semilla =
mismo nombre siempre), y lo usa tanto para el "huésped real" como para su
variación en el archivo de agencia. Si en el futuro F2 incorpora nombre de
huésped real, este generador puede leerlo directo en vez de derivarlo.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

AGENCY_NAMES = [
    "ViajaFacil", "SolyMar Tours", "EuroTrip Agency", "Andes Travel",
    "GlobalStay Agency", "CaribeViajes", "MontanaTours", "CostaBella Travel",
    "NorteSur Agencia", "Horizonte Viajes", "Rutas del Sur", "BlueSky Agency",
    "Destino Feliz", "Puerta del Sol Travel", "Viajes Amanecer",
]

FIRST_NAMES = ["Maria", "Carlos", "Ana", "John", "Laura", "Pedro", "Sofia", "Lucas",
               "Camila", "Diego", "Julia", "Marco", "Elena", "Rafael", "Patricia"]
LAST_NAMES = ["Garcia", "Silva", "Smith", "Lopez", "Santos", "Martinez", "Ferreira",
              "Rossi", "Fernandez", "Gomez", "Pereira", "Costa"]

AGENCY_COMMISSION_RATE = 0.10  # RN-02: agencia tradicional 10%


def _derive_guest_name(reservation_id: str) -> str:
    """Nombre determinístico derivado del reservation_id (ver nota del módulo)."""
    rng = random.Random(reservation_id)
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _vary_name(name: str, rng: random.Random) -> str:
    """
    Introduce una variación leve y realista en el nombre, del tipo que
    describe 5.3: "Reservas duplicadas entre canales con leves diferencias
    en el nombre." Por ejemplo: invertir orden, quitar tilde/segundo
    nombre, o un typo de una letra.
    """
    parts = name.split(" ")
    variation_type = rng.choice(["swap_order", "drop_accent_like", "typo", "middle_initial"])

    if variation_type == "swap_order" and len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    if variation_type == "middle_initial" and len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    if variation_type == "typo" and len(parts[-1]) > 3:
        last = list(parts[-1])
        idx = rng.randint(1, len(last) - 2)
        last[idx], last[idx - 1] = last[idx - 1], last[idx]  # swap de dos letras
        parts[-1] = "".join(last)
        return " ".join(parts)
    # drop_accent_like / fallback: minúsculas en el apellido, simulando
    # una transcripción distinta entre sistemas
    return f"{parts[0]} {parts[-1].lower()}"


@dataclass
class AgencyBooking:
    agency_booking_id: str
    agency_name: str
    hotel_id: str
    guest_name: str
    check_in: str
    check_out: str
    room_type: str
    currency: Optional[str]
    total_amount: float
    commission_rate: float
    duplicate_of_reservation_id: Optional[str] = None  # trazabilidad para pruebas, no es parte del "archivo real"


def _load_f2_reservations(f2_events_path: Path) -> list[dict]:
    """
    Carga las reservas 'created' emitidas por el generador de HU-24, para
    poder construir duplicados realistas contra ellas. Si el archivo no
    existe (por ejemplo, F2 aún no se ha corrido), el generador sigue
    funcionando pero sin poder construir el caso de duplicado cross-fuente.
    """
    if not f2_events_path.exists():
        return []

    reservations = []
    with f2_events_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev["event_type"] == "reservation.created":
                reservations.append(ev)
    return reservations


def generate_agency_files(
    output_dir: Path,
    f2_events_path: Path,
    seed: int = 7,
    bookings_per_agency: int = 12,
    duplicate_count: int = 3,
) -> dict:
    """
    Genera un CSV por agencia en output_dir. Devuelve un resumen (dict) con
    estadísticas, útil para validar AC2 sin tener que reabrir los CSV.

    `duplicate_count`: cuántas reservas de F2 se "clonan" como duplicados
    de agencia, repartidas entre agencias distintas.
    """
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    f2_reservations = _load_f2_reservations(f2_events_path)
    duplicate_sources = rng.sample(f2_reservations, k=min(duplicate_count, len(f2_reservations)))

    # AC2 depende por completo de que haya al menos una reserva de F2 para
    # clonar. Si el archivo de F2 no existe o está vacío, antes esto fallaba
    # en silencio (se generaban los 15 CSV sin ningún duplicado, sin avisar
    # nada). Ahora queda explícito en el propio resumen, para que un
    # "duplicates_created: []" inesperado sea fácil de diagnosticar.
    warning = None
    if not f2_events_path.exists():
        warning = f"El archivo de eventos F2 no existe: {f2_events_path}. Corre primero event_generator.py (HU-24)."
    elif not f2_reservations:
        warning = f"El archivo de eventos F2 existe pero no contiene eventos 'reservation.created': {f2_events_path}."
    elif duplicate_count > len(f2_reservations):
        warning = (f"Se pidieron {duplicate_count} duplicados pero solo hay {len(f2_reservations)} "
                   f"reservas 'created' disponibles en F2; se generaron {len(duplicate_sources)}.")

    summary = {"agencies": {}, "duplicates_created": [], "warning": warning}
    booking_counter = 0

    # columnas con nombres/orden levemente distintos por agencia, para
    # simular "formatos distintos" (5.2) sin inventar un parser nuevo por
    # agencia: usamos 2 layouts alternados.
    layout_a = ["agency_booking_id", "guest_name", "hotel_id", "check_in", "check_out",
                "room_type", "currency", "total_amount", "commission_rate"]
    layout_b = ["booking_ref", "hotel_id", "guest_full_name", "checkin_date", "checkout_date",
                "room_category", "amount", "currency", "commission_pct"]

    for agency_idx, agency_name in enumerate(AGENCY_NAMES, start=1):
        layout = layout_a if agency_idx % 2 == 0 else layout_b
        rows: list[AgencyBooking] = []

        for _ in range(bookings_per_agency):
            booking_counter += 1
            hotel_id = rng.choice([f"hotel-{i:03d}" for i in range(1, 29)])
            check_in = datetime(2026, 11, 1) + timedelta(days=rng.randint(0, 90))
            check_out = check_in + timedelta(days=rng.randint(1, 6))
            guest_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            room_type = rng.choice(["SINGLE", "DOUBLE", "TWIN", "SUITE"])
            # 5.3: "Monedas no indicadas en archivos de agencias" -> se deja
            # vacía deliberadamente en una fracción de filas; esa inyección
            # de defecto en tasa configurable es responsabilidad de HU-26,
            # aquí solo dejamos el campo nulleable para no bloquearla.
            currency = rng.choice(["EUR", "USD", None])
            total_amount = round(rng.uniform(80, 2000), 2)

            rows.append(AgencyBooking(
                agency_booking_id=f"AG{agency_idx:02d}-{booking_counter:05d}",
                agency_name=agency_name,
                hotel_id=hotel_id,
                guest_name=guest_name,
                check_in=check_in.strftime("%Y-%m-%d"),
                check_out=check_out.strftime("%Y-%m-%d"),
                room_type=room_type,
                currency=currency,
                total_amount=total_amount,
                commission_rate=AGENCY_COMMISSION_RATE,
            ))

        # --- inyectar 1 duplicado de F2 en esta agencia, si corresponde ---
        if duplicate_sources and agency_idx <= len(duplicate_sources):
            source_ev = duplicate_sources[agency_idx - 1]
            booking_counter += 1
            real_name = _derive_guest_name(source_ev["reservation_id"])
            varied_name = _vary_name(real_name, rng)
            data = source_ev["data"]

            dup_row = AgencyBooking(
                agency_booking_id=f"AG{agency_idx:02d}-{booking_counter:05d}",
                agency_name=agency_name,
                hotel_id=source_ev["hotel_id"],
                guest_name=varied_name,
                # ±1 día respecto a la reserva original, dentro de la
                # tolerancia que define RN-08 para considerarla duplicada
                check_in=(datetime.strptime(data["check_in"], "%Y-%m-%d") + timedelta(days=rng.choice([-1, 0, 1]))).strftime("%Y-%m-%d"),
                check_out=data["check_out"],
                room_type=data["room_type"],
                currency=data["currency"],
                total_amount=data["total_amount"],
                commission_rate=AGENCY_COMMISSION_RATE,
                duplicate_of_reservation_id=source_ev["reservation_id"],
            )
            rows.append(dup_row)
            summary["duplicates_created"].append({
                "agency": agency_name,
                "agency_booking_id": dup_row.agency_booking_id,
                "original_reservation_id": source_ev["reservation_id"],
                "original_channel": data["channel"],
                "real_guest_name": real_name,
                "agency_guest_name": varied_name,
                "hotel_id": dup_row.hotel_id,
            })

        # --- escribir CSV con el layout asignado a esta agencia ---
        file_path = output_dir / f"{agency_name.replace(' ', '_').lower()}_week.csv"
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(layout)
            for row in rows:
                if layout is layout_a:
                    writer.writerow([
                        row.agency_booking_id, row.guest_name, row.hotel_id,
                        row.check_in, row.check_out, row.room_type,
                        row.currency or "", row.total_amount, row.commission_rate,
                    ])
                else:
                    writer.writerow([
                        row.agency_booking_id, row.hotel_id, row.guest_name,
                        row.check_in, row.check_out, row.room_type,
                        row.total_amount, row.currency or "", row.commission_rate,
                    ])

        summary["agencies"][agency_name] = {
            "file": str(file_path),
            "rows": len(rows),
            "layout": "A" if layout is layout_a else "B",
        }

    return summary
