from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SERIES_IDS = (
    "CPIAUCSL,CPILFESL,PCEPI,PCEPILFE,DGS2,DGS10,FEDFUNDS,T10Y2Y,"
    "VIXCLS,SP500,NASDAQCOM,PAYEMS,UNRATE,UMCSENT,IPMAN,INDPRO,"
    "DGORDER,AMTMNO,DCOILWTICO"
)


def download_fred_graph_csv(series_id: str) -> list[dict[str, object]]:
    series_id = str(series_id or "").upper().strip()
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 research-autolab/1.0",
            "Accept": "text/csv,*/*",
        },
    )
    with urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    reader = csv.DictReader(text.splitlines())
    rows: list[dict[str, object]] = []

    for row in reader:
        date_text = (row.get("observation_date") or row.get("DATE") or "").strip()
        value_text = (row.get(series_id) or row.get("VALUE") or "").strip()
        if not date_text or value_text in {"", "."}:
            continue
        try:
            value = float(value_text)
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            continue
        rows.append({"date": date_text, "value": value})

    if not rows:
        raise RuntimeError(f"No usable FRED observations for {series_id}")

    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "value"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download FRED macro series CSVs for Research Autolab.")
    parser.add_argument("--series-ids", default=DEFAULT_SERIES_IDS)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("Live") / "data" / "autolab_macro",
        help="Output folder for SERIES_ID.csv files.",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    series_ids = [s.strip().upper() for s in args.series_ids.split(",") if s.strip()]

    ok: list[str] = []
    failed: dict[str, str] = {}

    for series_id in series_ids:
        try:
            rows = download_fred_graph_csv(series_id)
            path = out_dir / f"{series_id}.csv"
            write_csv(path, rows)
            ok.append(series_id)
            print(f"{series_id}: wrote {len(rows)} rows -> {path}")
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
            failed[series_id] = str(exc)
            print(f"{series_id}: failed: {exc}")

    print()
    print(f"Output directory: {out_dir}")
    print(f"Downloaded: {len(ok)}")
    if failed:
        print(f"Failed: {len(failed)}")
        for series_id, err in failed.items():
            print(f"- {series_id}: {err}")

    if not ok:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
