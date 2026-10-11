"""
US-25 / TASK 2 - CLI para generar los archivos semanales de agencias (F4)

Uso:
    python3 generate_agency_files.py \
        --f2-events ../channel_manager_simulator/output/events.jsonl \
        --output-dir output/agency_files \
        --seed 7 --bookings-per-agency 12 --duplicate-count 3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.agency_files import generate_agency_files


def main():
    parser = argparse.ArgumentParser(description="Genera archivos semanales de agencias (F4)")
    parser.add_argument("--f2-events", type=str,
                         default="../channel_manager_simulator/output/events.jsonl",
                         help="Ruta al events.jsonl generado por HU-24 (para construir duplicados reales)")
    parser.add_argument("--output-dir", type=str, default="output/agency_files")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bookings-per-agency", type=int, default=12)
    parser.add_argument("--duplicate-count", type=int, default=3,
                         help="Cuántas reservas de F2 se clonan como duplicados de agencia (AC2)")
    args = parser.parse_args()

    summary = generate_agency_files(
        output_dir=Path(args.output_dir),
        f2_events_path=Path(args.f2_events),
        seed=args.seed,
        bookings_per_agency=args.bookings_per_agency,
        duplicate_count=args.duplicate_count,
    )

    print(f"Generados {len(summary['agencies'])} archivos de agencia en {args.output_dir}")
    for agency, info in summary["agencies"].items():
        print(f"  - {agency}: {info['rows']} filas, layout {info['layout']} -> {info['file']}")

    print(f"\nDuplicados creados contra reservas de F2 (AC2): {len(summary['duplicates_created'])}")
    for dup in summary["duplicates_created"]:
        print(f"  - {dup['agency']} / {dup['agency_booking_id']} <-> F2 {dup['original_reservation_id']} "
              f"({dup['original_channel']}): '{dup['real_guest_name']}' vs '{dup['agency_guest_name']}'")

    summary_path = Path(args.output_dir) / "_generation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResumen guardado en: {summary_path}")


if __name__ == "__main__":
    main()
