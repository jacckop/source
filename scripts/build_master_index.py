#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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


MASTER_SOURCE: dict[str, Any] = {
    "name": "KiraStore",
    "identifier": "vip.kirastore.master",
    "subtitle": "KiraStore Master Source",
    "description": "Lite merged source generated automatically from KiraStore sources.",
    "website": "https://github.com/jacckop/source",
    "tintColor": "#D71920",
    "featuredApps": [],
    "apps": [],
}


HTTP_HEADERS = {
    "User-Agent": "KiraStore-IndexBuilder/7.0",
    "Accept": "application/json,text/plain,*/*",
}


APP_KEY_ALIASES = {
    "name": [
        "name",
        "title",
        "appName",
        "app_name",
    ],
    "bundleIdentifier": [
        "bundleIdentifier",
        "bundleID",
        "bundleId",
        "bundle",
        "identifier",
        "bundle_identifier",
        "bundleid",
        "package",
        "packageName",
    ],
    "subtitle": [
        "subtitle",
        "shortDescription",
        "short_description",
        "caption",
    ],
    "localizedDescription": [
        "localizedDescription",
        "description",
        "desc",
        "fullDescription",
        "full_description",
        "changelog",
    ],
    "iconURL": [
        "iconURL",
        "iconUrl",
        "icon",
        "icon_url",
        "image",
        "imageURL",
        "imageUrl",
        "artworkURL",
        "artworkUrl",
        "thumbnail",
    ],
    "tintColor": [
        "tintColor",
        "tint",
        "color",
    ],
    "category": [
        "category",
        "genre",
        "type",
    ],
    "downloadURL": [
        "downloadURL",
        "downloadUrl",
        "download_url",
        "download",
        "url",
        "ipa",
        "ipaURL",
        "ipaUrl",
        "ipa_url",
        "file",
        "fileURL",
        "fileUrl",
        "file_url",
        "link",
        "directLink",
        "direct_link",
    ],
    "version": [
        "version",
        "versionName",
        "version_name",
        "latestVersion",
        "latest_version",
        "build",
    ],
    "versionDate": [
        "versionDate",
        "date",
        "updatedDate",
        "updated",
        "lastUpdated",
        "last_updated",
        "created",
        "createdAt",
        "updated_at",
    ],
    "size": [
        "size",
        "Size",
        "SIZE",
        "sizeBytes",
        "size_bytes",
        "fileSize",
        "filesize",
        "file_size",
        "fileSizeBytes",
        "file_size_bytes",
        "ipaSize",
        "ipa_size",
        "appSize",
        "app_size",
        "downloadSize",
        "download_size",
        "binarySize",
        "binary_size",
        "ipaFileSize",
        "ipa_file_size",
        "file_size_in_bytes",
        "bytes",
        "length",
        "contentLength",
        "content_length",
    ],
    "minOSVersion": [
        "minOSVersion",
        "minimumOSVersion",
        "minimum_os_version",
        "minIOS",
        "minIOSVersion",
        "min_ios_version",
    ],
}


VERSION_KEY_ALIASES = {
    "version": [
        "version",
        "versionName",
        "version_name",
        "build",
    ],
    "downloadURL": [
        "downloadURL",
        "downloadUrl",
        "download_url",
        "download",
        "url",
        "ipa",
        "ipaURL",
        "ipaUrl",
        "ipa_url",
        "file",
        "fileURL",
        "fileUrl",
        "file_url",
        "link",
        "directLink",
        "direct_link",
    ],
    "date": [
        "date",
        "versionDate",
        "updatedDate",
        "updated",
        "lastUpdated",
        "last_updated",
        "created",
        "createdAt",
        "updated_at",
    ],
    "size": [
        "size",
        "Size",
        "SIZE",
        "sizeBytes",
        "size_bytes",
        "fileSize",
        "filesize",
        "file_size",
        "fileSizeBytes",
        "file_size_bytes",
        "ipaSize",
        "ipa_size",
        "appSize",
        "app_size",
        "downloadSize",
        "download_size",
        "binarySize",
        "binary_size",
        "ipaFileSize",
        "ipa_file_size",
        "file_size_in_bytes",
        "bytes",
        "length",
        "contentLength",
        "content_length",
    ],
    "minOSVersion": [
        "minOSVersion",
        "minimumOSVersion",
        "minimum_os_version",
        "minIOS",
        "minIOSVersion",
        "min_ios_version",
    ],
}


SIZE_CONTAINER_KEYS = [
    "size",
    "Size",
    "SIZE",
    "file",
    "ipa",
    "download",
    "metadata",
    "info",
    "asset",
    "binary",
    "version",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    value = value.replace("\u0000", "")
    return re.sub(r"\s+", " ", value).strip()


def first_value(data: dict[str, Any], aliases: list[str], default: Any = None) -> Any:
    for key in aliases:
        if key in data and data[key] not in (None, ""):
            return data[key]

    return default


def normalize_url(value: Any) -> str:
    return clean_text(value)


def safe_slug(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9]+", ".", text)
    text = re.sub(r"\.+", ".", text).strip(".")
    return text or "app"


def normalize_tint_color(value: Any) -> str:
    text = clean_text(value)

    if not text:
        return "#000000"

    if re.fullmatch(r"#?[0-9a-fA-F]{6}", text):
        return text if text.startswith("#") else f"#{text}"

    return "#000000"


def parse_size(value: Any) -> int:
    """
    يحوّل الحجم إلى بايت.
    يأخذ الحجم فقط إذا موجود بالسورس.
    لا يفحص رابط IPA.
    لا يخمّن.

    يدعم:
    42344934
    "42344934"
    "42 MB"
    "42.5MB"
    "1.2 GB"
    "1024 KB"
    """

    if value is None or value == "":
        return 0

    if isinstance(value, bool):
        return 0

    if isinstance(value, int):
        return value if value > 0 else 0

    if isinstance(value, float):
        return int(value) if value > 0 else 0

    if isinstance(value, dict):
        for key in VERSION_KEY_ALIASES["size"] + APP_KEY_ALIASES["size"]:
            if key in value:
                parsed = parse_size(value.get(key))
                if parsed > 0:
                    return parsed
        return 0

    if isinstance(value, list):
        for item in value:
            parsed = parse_size(item)
            if parsed > 0:
                return parsed
        return 0

    text = clean_text(value).replace(",", "")

    if not text:
        return 0

    if re.fullmatch(r"\d+", text):
        try:
            number = int(text)
            return number if number > 0 else 0
        except ValueError:
            return 0

    patterns = [
        r"([0-9]+(?:\.[0-9]+)?)\s*(BYTES?|B|KB|KIB|K|MB|MIB|M|GB|GIB|G|TB|TIB|T)",
        r"([0-9]+(?:\.[0-9]+)?)",
    ]

    match = None
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            break

    if not match:
        return 0

    number = float(match.group(1))
    unit = match.group(2).upper() if len(match.groups()) >= 2 and match.group(2) else "B"

    unit = unit.replace("IB", "B")

    multipliers = {
        "B": 1,
        "BYTE": 1,
        "BYTES": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
        "T": 1024**4,
        "TB": 1024**4,
    }

    size = int(number * multipliers.get(unit, 1))
    return size if size > 0 else 0


def deep_find_size(data: Any, depth: int = 0) -> int:
    """
    يبحث عن الحجم داخل أي مكان قريب من التطبيق أو النسخة.
    هذا مهم لأن بعض السورسات تخلي الحجم داخل:
    file.size
    ipa.size
    download.size
    metadata.size
    size.value
    """

    if depth > 4:
        return 0

    if isinstance(data, (int, float, str)):
        return parse_size(data)

    if isinstance(data, list):
        for item in data:
            parsed = deep_find_size(item, depth + 1)
            if parsed > 0:
                return parsed
        return 0

    if not isinstance(data, dict):
        return 0

    for key in VERSION_KEY_ALIASES["size"] + APP_KEY_ALIASES["size"]:
        if key in data:
            parsed = parse_size(data.get(key))
            if parsed > 0:
                return parsed

    for key in SIZE_CONTAINER_KEYS:
        nested = data.get(key)
        if isinstance(nested, (dict, list)):
            parsed = deep_find_size(nested, depth + 1)
            if parsed > 0:
                return parsed

    return 0


def remove_screenshot_content(value: Any) -> str:
    text = clean_text(value)

    if not text:
        return ""

    text = re.sub(
        r"https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    parts = re.split(r"(?<=[.!؟])\s+|\n+", text)
    cleaned_parts: list[str] = []

    bad_words = [
        "screenshot",
        "screenshots",
        "screen shot",
        "preview image",
        "preview images",
        "لقطة شاشة",
        "لقطات شاشة",
        "سكرين شوت",
        "سكرينشوت",
    ]

    for part in parts:
        low = part.lower()
        if any(word in low for word in bad_words):
            continue

        cleaned_parts.append(part)

    text = " ".join(cleaned_parts)

    text = re.sub(
        r"https?://\S*(?:screenshot|screenshots|preview)\S*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return clean_text(text)


def trim_text(value: Any, limit: int) -> str:
    text = remove_screenshot_content(value)

    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "..."


def fetch_json(url: str, retries: int = 3, timeout: int = 45) -> dict[str, Any] | list[Any]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers=HTTP_HEADERS)

            with urlopen(request, timeout=timeout) as response:
                raw = response.read()

            text = raw.decode("utf-8-sig", errors="replace").strip()

            if not text:
                raise ValueError("empty response")

            return json.loads(text)

        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            print(f"WARN: fetch failed {attempt}/{retries}: {url} -> {error}", file=sys.stderr)

            if attempt < retries:
                time.sleep(min(2 * attempt, 8))

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
        name = clean_text(source_json.get("name"))
        if name:
            return name

    parsed = urlparse(fallback_url)
    host = parsed.netloc.replace("www.", "")
    path_name = Path(parsed.path).name

    return host or path_name or fallback_url


def get_source_size(app_data: dict[str, Any], version_data: dict[str, Any]) -> int:
    """
    أولوية نقل الحجم:
    1. من النسخة نفسها.
    2. من التطبيق نفسه.
    3. من أي حقل nested قريب مثل file.size أو ipa.size.
    4. صفر.

    لا يوجد أي فحص لرابط IPA.
    """

    version_direct = first_value(version_data, VERSION_KEY_ALIASES["size"], None)
    version_size = parse_size(version_direct)

    if version_size > 0:
        return version_size

    app_direct = first_value(app_data, APP_KEY_ALIASES["size"], None)
    app_size = parse_size(app_direct)

    if app_size > 0:
        return app_size

    version_deep = deep_find_size(version_data)

    if version_deep > 0:
        return version_deep

    app_deep = deep_find_size(app_data)

    if app_deep > 0:
        return app_deep

    return 0


def normalize_version(version_data: dict[str, Any], app_data: dict[str, Any]) -> dict[str, Any]:
    version = clean_text(
        first_value(
            version_data,
            VERSION_KEY_ALIASES["version"],
            first_value(app_data, APP_KEY_ALIASES["version"], "1.0"),
        )
    ) or "1.0"

    download_url = normalize_url(
        first_value(
            version_data,
            VERSION_KEY_ALIASES["downloadURL"],
            first_value(app_data, APP_KEY_ALIASES["downloadURL"], ""),
        )
    )

    date_value = clean_text(
        first_value(
            version_data,
            VERSION_KEY_ALIASES["date"],
            first_value(app_data, APP_KEY_ALIASES["versionDate"], today()),
        )
    ) or today()

    size = get_source_size(app_data, version_data)

    output: dict[str, Any] = {
        "version": version,
        "date": date_value,
        "size": size,
    }

    if download_url:
        output["downloadURL"] = download_url

    min_os = clean_text(
        first_value(
            version_data,
            VERSION_KEY_ALIASES["minOSVersion"],
            first_value(app_data, APP_KEY_ALIASES["minOSVersion"], ""),
        )
    )

    if min_os:
        output["minOSVersion"] = min_os

    return output


def normalize_app(app: dict[str, Any], src_name: str, src_url: str) -> dict[str, Any] | None:
    name = clean_text(first_value(app, APP_KEY_ALIASES["name"], ""))

    if not name:
        return None

    top_download_url = normalize_url(first_value(app, APP_KEY_ALIASES["downloadURL"], ""))
    raw_versions = app.get("versions")

    versions: list[dict[str, Any]] = []

    if isinstance(raw_versions, list):
        for item in raw_versions:
            if isinstance(item, dict):
                version = normalize_version(item, app)

                if version.get("downloadURL") or top_download_url:
                    if not version.get("downloadURL") and top_download_url:
                        version["downloadURL"] = top_download_url

                    versions.append(version)

    if not versions and top_download_url:
        versions.append(normalize_version({}, app))

    if not versions:
        return None

    latest = versions[0]
    latest_download_url = normalize_url(latest.get("downloadURL")) or top_download_url

    if not latest_download_url:
        return None

    bundle = clean_text(first_value(app, APP_KEY_ALIASES["bundleIdentifier"], ""))

    if not bundle:
        seed = f"{name}|{latest_download_url}|{src_url}"
        bundle = f"vip.kirastore.unknown.{safe_slug(name)}.{sha1_text(seed)[:8]}"

    subtitle = trim_text(first_value(app, APP_KEY_ALIASES["subtitle"], src_name), 45)
    description = trim_text(first_value(app, APP_KEY_ALIASES["localizedDescription"], subtitle or name), 90)
    icon_url = normalize_url(first_value(app, APP_KEY_ALIASES["iconURL"], ""))
    tint_color = normalize_tint_color(first_value(app, APP_KEY_ALIASES["tintColor"], "#000000"))
    category = clean_text(first_value(app, APP_KEY_ALIASES["category"], ""))
    min_os = clean_text(first_value(app, APP_KEY_ALIASES["minOSVersion"], ""))

    final_size = parse_size(latest.get("size"))

    if final_size <= 0:
        final_size = get_source_size(app, raw_versions[0] if isinstance(raw_versions, list) and raw_versions and isinstance(raw_versions[0], dict) else {})

    latest["size"] = final_size

    output_version: dict[str, Any] = {
        "version": clean_text(latest.get("version")) or "1.0",
        "date": clean_text(latest.get("date")) or today(),
        "downloadURL": latest_download_url,
        "size": final_size,
    }

    if min_os:
        output_version["minOSVersion"] = min_os

    output: dict[str, Any] = {
        "name": name,
        "bundleIdentifier": bundle,
        "subtitle": subtitle,
        "localizedDescription": description,
        "iconURL": icon_url,
        "tintColor": tint_color,
        "size": final_size,
        "versions": [output_version],
    }

    if category:
        output["category"] = category

    if min_os:
        output["minOSVersion"] = min_os

    return output


def make_bundle_identifiers_unique(apps: list[dict[str, Any]]) -> int:
    bundle_counts: dict[str, int] = {}
    used_bundles: set[str] = set()
    changed = 0

    for app in apps:
        base_bundle = clean_text(app.get("bundleIdentifier"))

        if not base_bundle:
            seed = f"{app.get('name', '')}|{app.get('iconURL', '')}"
            base_bundle = f"vip.kirastore.unknown.{safe_slug(clean_text(app.get('name')))}.{sha1_text(seed)[:8]}"
            app["bundleIdentifier"] = base_bundle

        base_key = base_bundle.lower()
        next_number = bundle_counts.get(base_key, 0) + 1
        bundle_counts[base_key] = next_number

        candidate = base_bundle if next_number == 1 else f"{base_bundle}.{next_number}"

        while candidate.lower() in used_bundles:
            next_number += 1
            bundle_counts[base_key] = next_number
            candidate = f"{base_bundle}.{next_number}"

        if candidate != base_bundle:
            app["bundleIdentifier"] = candidate
            changed += 1

        used_bundles.add(candidate.lower())

    return changed


def app_sort_key(app: dict[str, Any]) -> tuple[str, str]:
    return (
        clean_text(app.get("name")).lower(),
        clean_text(app.get("bundleIdentifier")).lower(),
    )


def build_index() -> tuple[dict[str, Any], dict[str, Any]]:
    all_apps: list[dict[str, Any]] = []

    report: dict[str, Any] = {
        "generatedAt": utc_now(),
        "sourceCount": len(SOURCES),
        "sources": [],
        "totalFetchedApps": 0,
        "totalNormalizedApps": 0,
        "totalSkippedApps": 0,
        "totalOutputApps": 0,
        "bundleIdentifierRenamedApps": 0,
        "appsWithSize": 0,
        "appsWithoutSize": 0,
        "errors": [],
    }

    for url in SOURCES:
        source_report = {
            "url": url,
            "name": "",
            "fetchedApps": 0,
            "normalizedApps": 0,
            "skippedApps": 0,
            "withSize": 0,
            "withoutSize": 0,
            "error": "",
        }

        try:
            source_json = fetch_json(url)
            src_name = source_name(source_json, url)
            raw_apps = extract_apps(source_json)

            source_report["name"] = src_name
            source_report["fetchedApps"] = len(raw_apps)
            report["totalFetchedApps"] += len(raw_apps)

            for raw_app in raw_apps:
                normalized = normalize_app(raw_app, src_name, url)

                if normalized is None:
                    source_report["skippedApps"] += 1
                    report["totalSkippedApps"] += 1
                    continue

                if parse_size(normalized.get("size")) > 0:
                    source_report["withSize"] += 1
                    report["appsWithSize"] += 1
                else:
                    source_report["withoutSize"] += 1
                    report["appsWithoutSize"] += 1

                all_apps.append(normalized)
                source_report["normalizedApps"] += 1
                report["totalNormalizedApps"] += 1

            print(
                f"OK: {src_name} | fetched={source_report['fetchedApps']} "
                f"normalized={source_report['normalizedApps']} "
                f"withSize={source_report['withSize']} "
                f"withoutSize={source_report['withoutSize']} "
                f"skipped={source_report['skippedApps']}"
            )

        except Exception as error:
            message = f"{url}: {error}"
            print(f"ERROR: {message}", file=sys.stderr)
            source_report["error"] = str(error)
            report["errors"].append(message)

        report["sources"].append(source_report)

    renamed_count = make_bundle_identifiers_unique(all_apps)

    for app in all_apps:
        size = parse_size(app.get("size"))
        app["size"] = size

        versions = app.get("versions")

        if isinstance(versions, list) and versions and isinstance(versions[0], dict):
            versions[0]["size"] = size

    all_apps.sort(key=app_sort_key)

    featured_apps: list[str] = []

    for app in all_apps:
        bundle = clean_text(app.get("bundleIdentifier"))

        if bundle and bundle not in featured_apps:
            featured_apps.append(bundle)

        if len(featured_apps) >= 20:
            break

    output = dict(MASTER_SOURCE)
    output["apps"] = all_apps
    output["featuredApps"] = featured_apps

    report["totalOutputApps"] = len(all_apps)
    report["bundleIdentifierRenamedApps"] = renamed_count

    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lite merged KiraStore source.")
    parser.add_argument("--output", default="dist/kirastore-index.json", help="Output JSON path")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON. This increases file size.")

    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data, report = build_index()

    if args.pretty:
        json_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    else:
        json_text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"

    output_path.write_text(json_text, encoding="utf-8")

    file_size_mb = output_path.stat().st_size / 1024 / 1024

    print("\nBuild report:")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote: {output_path}")
    print(f"Apps: {len(data.get('apps', []))}")
    print(f"File size: {file_size_mb:.2f} MB")
    print(f"Renamed duplicate bundle identifiers: {report.get('bundleIdentifierRenamedApps', 0)}")
    print(f"Apps with size: {report.get('appsWithSize', 0)}")
    print(f"Apps without size: {report.get('appsWithoutSize', 0)}")

    if report.get("errors"):
        print("\nSome sources failed, but the merged source was still generated.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
