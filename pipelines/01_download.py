"""
01_download.py — Stage raw Ethiopian data into data/raw/.

Usage:
    conda run -n eth-health-access python pipelines/01_download.py
    conda run -n eth-health-access python pipelines/01_download.py --force

Every file is recorded in data/raw/manifest.json with URL, bytes,
SHA-256, license and UTC timestamp. Re-running skips existing files
unless --force.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from tqdm import tqdm

RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)
MANIFEST = RAW / "manifest.json"
UA = {"User-Agent": "eth-health-access/0.1 (research)"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False))


def record(key: str, path: Path, url: str, license_: str) -> None:
    m = load_manifest()
    m[key] = {
        "filename": str(path.relative_to(RAW)).replace("\\", "/"),
        "url": url,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "license": license_,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(m)
    print(f"  manifest <- {key}  ({path.stat().st_size:,} bytes)")


def download(url: str, dest: Path, retries: int = 4) -> None:
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=UA, stream=True, timeout=180) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True, desc=dest.name
                ) as bar:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        bar.update(len(chunk))
                tmp.replace(dest)
                return
        except Exception as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            print(f"  ! {exc} — retry {attempt}/{retries} in {wait}s", file=sys.stderr)
            time.sleep(wait)


# ---------------------------------------------------------------- sources
def fetch_osm(force: bool) -> None:
    url = "https://download.geofabrik.de/africa/ethiopia-latest.osm.pbf"
    dest = RAW / "ethiopia-latest.osm.pbf"
    print("\n=== OSM Ethiopia (Geofabrik) ===")
    if dest.exists() and not force:
        print(f"= exists: {dest.name} ({dest.stat().st_size:,} bytes)")
    else:
        download(url, dest)
    record("osm_pbf", dest, url, "ODbL 1.0 (OpenStreetMap contributors)")


def fetch_hdx_facilities(force: bool) -> None:
    pkg_id = "ethiopian-health-facilities"
    api = "https://data.humdata.org/api/3/action/package_show"
    print(f"\n=== HDX health facilities ({pkg_id}) ===")
    r = requests.get(api, params={"id": pkg_id}, headers=UA, timeout=60)
    r.raise_for_status()
    resources = r.json()["result"]["resources"]

    prefer = ["SHP", "GeoJSON", "CSV", "ZIP"]
    def rank(res):
        fmt = (res.get("format") or "").upper()
        try:
            return prefer.index(fmt)
        except ValueError:
            return len(prefer)

    chosen = None
    for res in sorted(resources, key=rank):
        fmt = (res.get("format") or "").upper()
        if fmt in prefer and res.get("download_url"):
            chosen = res
            break
    if not chosen:
        raise RuntimeError(f"No SHP/GeoJSON/CSV resource on HDX package {pkg_id}")

    url = chosen["download_url"]
    name = chosen.get("name") or Path(url).name
    dest = RAW / "facilities" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  chosen: {name}  ({chosen.get('format')})")
    if dest.exists() and not force:
        print(f"= exists: {dest.name} ({dest.stat().st_size:,} bytes)")
    else:
        download(url, dest)
    record("facilities", dest, url, chosen.get("license") or "See HDX dataset page")


def fetch_geoboundaries(force: bool) -> None:
    iso3 = "ETH"
    print("\n=== geoBoundaries ADM0–3 ===")
    for lvl in ["ADM0", "ADM1", "ADM2", "ADM3"]:
        api = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/{lvl}/"
        try:
            r = requests.get(api, headers=UA, timeout=60)
            r.raise_for_status()
            info = r.json()
        except Exception as exc:
            print(f"  ! {lvl}: API error: {exc}", file=sys.stderr)
            continue
        url = info.get("gjDownloadURL") or info.get("staticDownloadLink")
        if not url:
            print(f"  ! {lvl}: no download link in API response", file=sys.stderr)
            continue
        dest = RAW / "adm" / f"{iso3}_{lvl}.geojson"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            print(f"= exists: {dest.name} ({dest.stat().st_size:,} bytes)")
        else:
            print(f"+ {lvl}: {url}")
            download(url, dest)
        record(f"adm_{lvl}", dest, url, "CC-BY 4.0 (geoBoundaries)")


def fetch_worldpop(force: bool) -> None:
    print("\n=== WorldPop Ethiopia 2020 (constrained, 100 m) ===")
    candidates = [
        "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/ETH/eth_ppp_2020_UNadj_constrained.tif",
        "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/ETH/eth_ppp_2020_UNadj_constrained.tif",
    ]
    dest = RAW / "eth_ppp_2020_UNadj_constrained.tif"
    if dest.exists() and not force:
        print(f"= exists: {dest.name} ({dest.stat().st_size:,} bytes)")
        record("worldpop_2020", dest, "cached", "CC-BY 4.0 (WorldPop)")
        return
    last_err = None
    for url in candidates:
        try:
            print(f"  trying: {url}")
            download(url, dest)
            record("worldpop_2020", dest, url, "CC-BY 4.0 (WorldPop)")
            return
        except Exception as exc:
            last_err = exc
            print(f"  ! failed: {exc}", file=sys.stderr)
    raise RuntimeError(f"All WorldPop candidate URLs failed. Last: {last_err}")


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    print(f"Data root: {RAW.resolve()}")
    steps = [
        ("OSM",           fetch_osm),
        ("HDX facilities", fetch_hdx_facilities),
        ("geoBoundaries", fetch_geoboundaries),
        ("WorldPop",      fetch_worldpop),
    ]
    failures = []
    for name, fn in steps:
        try:
            fn(args.force)
        except Exception as exc:
            print(f"FAILED {name}: {exc}", file=sys.stderr)
            failures.append(name)

    print("\n" + "=" * 60)
    print(f"Downloaded/skipped: {len(steps) - len(failures)}/{len(steps)}")
    if failures:
        print(f"FAILURES: {failures}")
        return 1
    print(f"Manifest: {MANIFEST.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())