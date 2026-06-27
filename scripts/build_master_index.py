#!/usr/bin/env python3
"""
Build KiraStore Master Index

This script fetches multiple AltStore/Feather-compatible sources, normalizes their
apps, and writes one merged source JSON file WITHOUT deleting duplicate apps.

Important policy:
- No app is removed because it is duplicated.
- If more than one app has the same bundleIdentifier, the first one keeps the
  original bundleIdentifier, and the next ones get numbers added at the end:
    com.example.app
    com.example.app.2
    com.example.app.3
- The original value is preserved in originalBundleIdentifier.

Output example:
  dist/kirastore-index.json

Raw source link after the Action commits the file:
  https://raw.githubusercontent.com/OWNER/REPO/main/dist/kirastore-index.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# كل سورساتك الحالية
SOURCES: list[str] = [
    "https://raw.githubusercontent.com/jacckop/source/main/ipastore",
    "https://raw.githubusercontent.com/jacckop/source/main/AppTesters",
    "https://fastsign.dev/repo.lite.json",
    "https://fastsign.dev/repo.json",
    "https://raw.githubusercontent.com/jacckop/source/main/iraq",
    "https://raw.githubusercontent.com/jacckop/source/main/mthk",
    "https://repository.apptesters.org",
    "https://ipa.cypwn.xyz/cypwn.json",
    "https://source.ryuksign.com",
    "https://raw.githubusercontent.com/jacckop/source/main/multi",
    "https://raw.githubusercontent.com/jacckop/source/main/develek",
    "https://raw.githubusercontent.com/jacckop/source/main/sidelix",
    "https://raw.githubusercontent.com/jacckop/source/main/resource/sorse_part1.json",
    "https://raw.githubusercontent.com/jacckop/source/main/resource/sorse_part2.json",
    "https://raw.githubusercontent.com/jacckop/source/main/resource/sorse_part3.json",
    "https://raw.githubusercontent.com/jacckop/source/main/resource/sorse_part4.json",
    "https://raw.githubusercontent.com/jacckop/source/main/resource/sorse_part5.json",
]

# اسم السورس الموحد النهائي
MASTER_SOURCE: dict[str, Any] = {
    "name": "KiraStore",
    "identifier": "vip.kirastore.master",
    "subtitle": "KiraStore Master Source",
    "description": "Merged app source generated automatically from KiraStore sources. Duplicate apps are kept, and duplicate bundle identifiers are renamed with numbers.",
    "website": "https://github.com/jacckop/source",
    "tintColor": "#D71920",
    "featuredApps": [],
    "apps": [],
    "news": [],
}

HTTP_HEADERS = {
    "User-Agent": "KiraStore-IndexBuilder/1.1 (+https://github.com/jacckop/source)",
    "Accept": "application/json,text/plain,*/*",
}

APP_KEY_ALIASES = {
    "name": ["name", "title", "appName"],
    "bundleIdentifier": ["bundleIdentifier", "bundleID", "bundleId", "bundle", "identifier"],
    "developerName": ["developerName", "developer", "author"],
    "subtitle": ["subtitle", "shortDescription"],
    "localizedDescription": ["localizedDescription", "description", "desc"],
    "iconURL": ["iconURL", "iconUrl", "icon", "icon_url", "image", "imageURL", "imageUrl"],
    "tintColor": ["tintColor", "tint"],
    "category": ["category", "genre"],
    "downloadURL": ["downloadURL", "downloadUrl", "download", "url", "ipa", "ipaURL", "ipaUrl"],
    "version": ["version", "versionName", "latestVersion"],
    "versionDate": ["versionDate", "date", "updatedDate", "updated", "lastUpdated"],
    "size": ["size", "sizeBytes", "fileSize", "fileSizeBytes"],
    "minOSVersion": ["minOSVersion", "minimumOSVersion", "minIOS", "minIOSVersion"],
}

VERSION_KEY_ALIASES = {
    "version": ["version", "versionName"],
    "downloadURL": ["downloadURL", "downloadUrl", "download", "url", "ipa", "ipaURL", "ipaUrl"],
    "date": ["date", "versionDate", "updatedDate", "updated", "lastUpdated"],
    "localizedDescription": ["localizedDescription", "description", "desc", "changelog"],
    "size": ["size", "sizeBytes", "fileSize", "fileSizeBytes"],
    "minOSVersion": ["minOSVersion", "minimumOSVersion", "minIOS", "minIOSVersion"],
    "maxOSVersion": ["maxOSVersion", "maximumOSVersion", "maxIOS", "maxIOSVersion"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value).strip()


def first_value(data: dict[str, Any], aliases: list[str], default: Any = None) -> Any:
    for key in aliases:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def normalize_url(value: Any) -> str:
    value = clean_text(value)
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return value


def parse_size(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None

    text = clean_text(value).replace(",", "")
    if not text:
        return None

    # Already bytes as text
    if re.fullmatch(r"\d+", text):
        try:
            return int(text)
        except ValueError:
            return None

    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?I?B|[KMGT])?", text, re.I)
    if not match:
        return None

    number = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    unit = unit.replace("IB", "B")

    multipliers = {
        "B": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
        "T": 1024**4,
        "TB": 1024**4,
    }
    return int(number * multipliers.get(unit, 1))


def safe_slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", ".", text)
    text = re.sub(r"\.+", ".", text).strip(".")
    return text or "app"


def fetch_json(url: str, retries: int = 3, timeout: int = 35) -> dict[str, Any] | list[Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=HTTP_HEADERS)
            with urlopen(req, timeout=timeout) as response:
                raw = response.read()
            text = raw.decode("utf-8-sig", errors="replace").strip()
            if not text:
                raise ValueError("empty response")
            return json.loads(text)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            wait = min(2 * attempt, 8)
            print(f"WARN: fetch failed attempt {attempt}/{retries}: {url} -> {error}", file=sys.stderr)
            if attempt < retries:
                time.sleep(wait)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def extract_apps(source_json: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(source_json, list):
        return [item for item in source_json if isinstance(item, dict)]
    if not isinstance(source_json, dict):
        return []

    apps = source_json.get("apps")
    if isinstance(apps, list):
        return [item for item in apps if isinstance(item, dict)]
    if isinstance(apps, dict):
        return [item for item in apps.values() if isinstance(item, dict)]

    # Some custom repos put apps inside "data".
    data = source_json.get("data")
    if isinstance(data, dict):
        nested_apps = data.get("apps")
        if isinstance(nested_apps, list):
            return [item for item in nested_apps if isinstance(item, dict)]
        if isinstance(nested_apps, dict):
            return [item for item in nested_apps.values() if isinstance(item, dict)]

    return []


def source_name(source_json: dict[str, Any] | list[Any], fallback_url: str) -> str:
    if isinstance(source_json, dict):
        value = clean_text(source_json.get("name"))
        if value:
            return value
    host = urlparse(fallback_url).netloc.replace("www.", "")
    path = Path(urlparse(fallback_url).path).name
    return host or path or fallback_url


def normalize_version(version_data: dict[str, Any], app_data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = deepcopy(version_data)

    version = clean_text(first_value(version_data, VERSION_KEY_ALIASES["version"], first_value(app_data, APP_KEY_ALIASES["version"], "1.0")))
    download_url = normalize_url(first_value(version_data, VERSION_KEY_ALIASES["downloadURL"], first_value(app_data, APP_KEY_ALIASES["downloadURL"], "")))
    date = clean_text(first_value(version_data, VERSION_KEY_ALIASES["date"], first_value(app_data, APP_KEY_ALIASES["versionDate"], utc_now().split("T")[0])))
    description = clean_text(first_value(version_data, VERSION_KEY_ALIASES["localizedDescription"], first_value(app_data, APP_KEY_ALIASES["localizedDescription"], "")))
    size = parse_size(first_value(version_data, VERSION_KEY_ALIASES["size"], first_value(app_data, APP_KEY_ALIASES["size"], None)))

    normalized["version"] = version or "1.0"
    if download_url:
        normalized["downloadURL"] = download_url
    if date:
        normalized["date"] = date
    if description:
        normalized["localizedDescription"] = description
    if size is not None:
        normalized["size"] = size

    min_os = clean_text(first_value(version_data, VERSION_KEY_ALIASES["minOSVersion"], first_value(app_data, APP_KEY_ALIASES["minOSVersion"], "")))
    if min_os:
        normalized["minOSVersion"] = min_os

    max_os = clean_text(first_value(version_data, VERSION_KEY_ALIASES["maxOSVersion"], ""))
    if max_os:
        normalized["maxOSVersion"] = max_os

    return normalized


def normalize_app(app: dict[str, Any], src_name: str, src_url: str) -> dict[str, Any] | None:
    app = deepcopy(app)

    name = clean_text(first_value(app, APP_KEY_ALIASES["name"], ""))
    if not name:
        return None

    download_url = normalize_url(first_value(app, APP_KEY_ALIASES["downloadURL"], ""))
    raw_versions = app.get("versions")

    versions: list[dict[str, Any]] = []
    if isinstance(raw_versions, list):
        for item in raw_versions:
            if isinstance(item, dict):
                normalized_version = normalize_version(item, app)
                if normalized_version.get("downloadURL") or download_url:
                    versions.append(normalized_version)

    if not versions and download_url:
        versions.append(normalize_version({}, app))

    # Skip entries that do not have any downloadable IPA URL.
    if not versions and not download_url:
        return None

    bundle = clean_text(first_value(app, APP_KEY_ALIASES["bundleIdentifier"], ""))
    if not bundle:
        seed = f"{name}|{download_url}|{src_url}"
        bundle = f"vip.kirastore.unknown.{safe_slug(name)}.{sha1_text(seed)[:8]}"

    normalized: dict[str, Any] = deepcopy(app)
    normalized["name"] = name
    normalized["bundleIdentifier"] = bundle
    normalized["developerName"] = clean_text(first_value(app, APP_KEY_ALIASES["developerName"], "KiraStore")) or "KiraStore"

    subtitle = clean_text(first_value(app, APP_KEY_ALIASES["subtitle"], ""))
    if subtitle:
        normalized["subtitle"] = subtitle

    description = clean_text(first_value(app, APP_KEY_ALIASES["localizedDescription"], subtitle or name))
    if description:
        normalized["localizedDescription"] = description

    icon_url = normalize_url(first_value(app, APP_KEY_ALIASES["iconURL"], ""))
    if icon_url:
        normalized["iconURL"] = icon_url

    tint = clean_text(first_value(app, APP_KEY_ALIASES["tintColor"], ""))
    if tint:
        normalized["tintColor"] = tint

    category = clean_text(first_value(app, APP_KEY_ALIASES["category"], "Utilities")) or "Utilities"
    normalized["category"] = category

    # Keep top-level downloadURL/version for clients that use custom formats.
    latest = versions[0] if versions else {}
    if latest.get("downloadURL"):
        normalized["downloadURL"] = latest["downloadURL"]
    if latest.get("version"):
        normalized["version"] = latest["version"]
    if latest.get("size") is not None:
        normalized["size"] = latest["size"]

    # لا نحذف أي نسخة من versions. نخليها مثل ما جايه بعد التوحيد.
    normalized["versions"] = versions

    # Extra metadata. Swift Decodable normally ignores unknown fields, but this helps you debug the source.
    normalized["sourceName"] = src_name
    normalized["sourceURL"] = src_url

    return normalized


def make_bundle_identifiers_unique(apps: list[dict[str, Any]]) -> int:
    """
    Keep every app, but prevent identical bundleIdentifier values.

    Example:
      com.demo.app
      com.demo.app.2
      com.demo.app.3

    Returns the number of apps whose bundleIdentifier was changed.
    """
    bundle_counts: dict[str, int] = {}
    used_bundles: set[str] = set()
    changed = 0

    for app in apps:
        base_bundle = clean_text(app.get("bundleIdentifier"))
        if not base_bundle:
            seed = f"{app.get('name', '')}|{app.get('downloadURL', '')}|{app.get('sourceURL', '')}"
            base_bundle = f"vip.kirastore.unknown.{safe_slug(clean_text(app.get('name')))}.{sha1_text(seed)[:8]}"
            app["bundleIdentifier"] = base_bundle

        base_key = base_bundle.lower()
        next_number = bundle_counts.get(base_key, 0) + 1
        bundle_counts[base_key] = next_number

        candidate = base_bundle if next_number == 1 else f"{base_bundle}.{next_number}"

        # Extra safety: avoid collision with an existing real bundle like com.demo.app.2
        while candidate.lower() in used_bundles:
            next_number += 1
            bundle_counts[base_key] = next_number
            candidate = f"{base_bundle}.{next_number}"

        if candidate != base_bundle:
            app["originalBundleIdentifier"] = base_bundle
            app["bundleIdentifier"] = candidate
            changed += 1

        used_bundles.add(candidate.lower())

    return changed


def latest_version(app: dict[str, Any]) -> str:
    versions = app.get("versions")
    if isinstance(versions, list) and versions:
        first = versions[0]
        if isinstance(first, dict):
            return clean_text(first.get("version")) or clean_text(app.get("version")) or "1.0"
    return clean_text(app.get("version")) or "1.0"


def build_index() -> tuple[dict[str, Any], dict[str, Any]]:
    all_apps: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "generatedAt": utc_now(),
        "sources": [],
        "totalFetchedApps": 0,
        "totalNormalizedApps": 0,
        "totalSkippedApps": 0,
        "totalOutputApps": 0,
        "bundleIdentifierRenamedApps": 0,
        "errors": [],
    }

    for source_index, url in enumerate(SOURCES):
        source_report = {
            "url": url,
            "name": "",
            "fetchedApps": 0,
            "normalizedApps": 0,
            "skippedApps": 0,
            "error": "",
        }

        try:
            source_json = fetch_json(url)
            src_name = source_name(source_json, url)
            apps = extract_apps(source_json)
            source_report["name"] = src_name
            source_report["fetchedApps"] = len(apps)
            report["totalFetchedApps"] += len(apps)

            for app_index, raw_app in enumerate(apps):
                normalized = normalize_app(raw_app, src_name, url)
                if not normalized:
                    source_report["skippedApps"] += 1
                    report["totalSkippedApps"] += 1
                    continue

                normalized["sourceIndex"] = source_index
                normalized["sourceAppIndex"] = app_index
                all_apps.append(normalized)

                source_report["normalizedApps"] += 1
                report["totalNormalizedApps"] += 1

            print(
                f"OK: {src_name} -> fetched={source_report['fetchedApps']} "
                f"normalized={source_report['normalizedApps']} skipped={source_report['skippedApps']}"
            )

        except Exception as error:  # Keep building even if one source fails.
            message = f"{url}: {error}"
            print(f"ERROR: {message}", file=sys.stderr)
            source_report["error"] = str(error)
            report["errors"].append(message)

        report["sources"].append(source_report)

    renamed_count = make_bundle_identifiers_unique(all_apps)

    # ترتيب موحد وواضح: حسب الاسم، ثم النسخة، ثم المصدر.
    all_apps.sort(
        key=lambda item: (
            clean_text(item.get("name")).lower(),
            latest_version(item).lower(),
            clean_text(item.get("sourceName")).lower(),
            clean_text(item.get("bundleIdentifier")).lower(),
        )
    )

    output = deepcopy(MASTER_SOURCE)
    output["apps"] = all_apps
    output["news"] = [
        {
            "title": "KiraStore Master Index Updated",
            "identifier": f"vip.kirastore.master.update.{utc_now()}",
            "caption": f"Updated automatically. Apps: {len(all_apps)}. Renamed duplicate bundle IDs: {renamed_count}",
            "date": utc_now(),
            "tintColor": "#D71920",
            "notify": False,
        }
    ]

    # Put a small list of featured apps by taking the first valid bundle IDs.
    featured: list[str] = []
    for app in all_apps:
        bundle = clean_text(app.get("bundleIdentifier"))
        if bundle and not bundle.startswith("vip.kirastore.unknown.") and bundle not in featured:
            featured.append(bundle)
        if len(featured) >= 20:
            break
    output["featuredApps"] = featured

    report["totalOutputApps"] = len(all_apps)
    report["bundleIdentifierRenamedApps"] = renamed_count
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one merged KiraStore source JSON without deleting duplicate apps.")
    parser.add_argument("--output", default="dist/kirastore-index.json", help="Output JSON path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON. Compact is smaller and faster for apps.")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data, report = build_index()

    if args.pretty:
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        output_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    print("\nBuild report:")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote: {output_path}")
    print(f"Apps: {len(data.get('apps', []))}")
    print(f"Renamed duplicate bundle IDs: {report.get('bundleIdentifierRenamedApps', 0)}")
    if report.get("errors"):
        print("\nSome sources failed, but the merged source was still generated.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
