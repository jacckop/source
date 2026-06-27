#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlsplit, urlunsplit
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
    "User-Agent": "KiraStore-IndexBuilder/6.0",
    "Accept": "application/json,text/plain,*/*",
}


APP_KEY_ALIASES = {
    "name": ["name", "title", "appName"],
    "bundleIdentifier": ["bundleIdentifier", "bundleID", "bundleId", "bundle", "identifier"],
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
    "size": ["size", "sizeBytes", "fileSize", "fileSizeBytes"],
    "minOSVersion": ["minOSVersion", "minimumOSVersion", "minIOS", "minIOSVersion"],
}


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


def safe_url_for_request(url: str) -> str:
    """
    يحوّل المسافات والرموز غير المرمزة داخل الرابط حتى urllib يقدر يفحص الحجم.
    هذا لا يغيّر الرابط المحفوظ داخل JSON، فقط يستخدم للفحص.
    """

    url = normalize_url(url)

    if not url:
        return ""

    try:
        parts = urlsplit(url)
        path = quote(parts.path, safe="/:%@+")
        query = quote(parts.query, safe="=&:%@+/?")
        fragment = quote(parts.fragment, safe="")
        return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))
    except Exception:
        return url.replace(" ", "%20")


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
    يحوّل الحجم إلى بايت بصيغة رقم:
    42344934
    "42344934"
    "42 MB"
    "42.5 MB"
    "1.2 GB"

    إذا الحجم غير موجود أو صفر يرجع 0.
    """

    if value is None or value == "":
        return 0

    if isinstance(value, bool):
        return 0

    if isinstance(value, int):
        return value if value > 0 else 0

    if isinstance(value, float):
        return int(value) if value > 0 else 0

    text = clean_text(value).replace(",", "")
    if not text:
        return 0

    if re.fullmatch(r"\d+", text):
        try:
            number = int(text)
            return number if number > 0 else 0
        except ValueError:
            return 0

    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?I?B|[KMGT]|BYTES?)?", text, re.I)

    if not match:
        return 0

    number = float(match.group(1))
    unit = (match.group(2) or "B").upper()
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


def fetch_remote_size(url: str, timeout: int = 15) -> int:
    """
    يجيب الحجم الحقيقي من السيرفر إذا السورس كاتب الحجم صفر أو ما كاتبه.
    هذا مو تخمين. يعتمد على:
    - Content-Length
    - Content-Range

    إذا السيرفر ما يرجع حجم يرجع 0.
    """

    request_url = safe_url_for_request(url)

    if not request_url.startswith("http://") and not request_url.startswith("https://"):
        return 0

    headers = {
        "User-Agent": "KiraStore-SizeFetcher/6.0",
        "Accept": "*/*",
    }

    try:
        request = Request(request_url, headers=headers, method="HEAD")

        with urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")

            if length and length.isdigit():
                size = int(length)

                if size > 0:
                    return size
    except Exception:
        pass

    try:
        headers["Range"] = "bytes=0-0"
        request = Request(request_url, headers=headers, method="GET")

        with urlopen(request, timeout=timeout) as response:
            content_range = response.headers.get("Content-Range", "")
            match = re.search(r"/(\d+)$", content_range)

            if match:
                size = int(match.group(1))

                if size > 0:
                    return size

            length = response.headers.get("Content-Length")

            if length and length.isdigit():
                size = int(length)

                if size > 1:
                    return size
    except Exception:
        pass

    return 0


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
    version_size = parse_size(first_value(version_data, VERSION_KEY_ALIASES["size"], None))

    if version_size > 0:
        return version_size

    app_size = parse_size(first_value(app_data, APP_KEY_ALIASES["size"], None))

    if app_size > 0:
        return app_size

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

    app_size = parse_size(first_value(app, APP_KEY_ALIASES["size"], None))
    version_size = parse_size(latest.get("size"))
    final_size = version_size if version_size > 0 else app_size

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


def fill_missing_sizes(apps: list[dict[str, Any]], max_workers: int = 40) -> int:
    """
    يملأ الحجوم الناقصة فقط:
    - إذا الحجم من السورس موجود، ما يغيره.
    - إذا الحجم 0، يفحص رابط IPA ويأخذ Content-Length.
    - إذا السيرفر ما رجع حجم، يبقى 0.
    """

    targets: list[tuple[int, str]] = []

    for index, app in enumerate(apps):
        app_size = parse_size(app.get("size"))

        versions = app.get("versions")
        version = versions[0] if isinstance(versions, list) and versions and isinstance(versions[0], dict) else {}

        version_size = parse_size(version.get("size")) if isinstance(version, dict) else 0
        download_url = clean_text(version.get("downloadURL")) if isinstance(version, dict) else ""

        if app_size <= 0 and version_size <= 0 and download_url:
            targets.append((index, download_url))

    if not targets:
        return 0

    print(f"Fetching real sizes for {len(targets)} apps with missing size...")

    updated = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_remote_size, url): index
            for index, url in targets
        }

        for future in as_completed(futures):
            index = futures[future]

            try:
                size = future.result()
            except Exception:
                size = 0

            if size <= 0:
                continue

            app = apps[index]
            app["size"] = size

            versions = app.get("versions")

            if isinstance(versions, list) and versions and isinstance(versions[0], dict):
                versions[0]["size"] = size

            updated += 1

    print(f"Real sizes updated: {updated}/{len(targets)}")
    return updated


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


def build_index(fill_sizes: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
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
        "appsWithSourceSize": 0,
        "appsWithoutSourceSize": 0,
        "remoteSizesUpdated": 0,
        "appsWithFinalSize": 0,
        "appsWithoutFinalSize": 0,
        "errors": [],
    }

    for url in SOURCES:
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
                    report["appsWithSourceSize"] += 1
                else:
                    report["appsWithoutSourceSize"] += 1

                all_apps.append(normalized)
                source_report["normalizedApps"] += 1
                report["totalNormalizedApps"] += 1

            print(
                f"OK: {src_name} | fetched={source_report['fetchedApps']} "
                f"normalized={source_report['normalizedApps']} skipped={source_report['skippedApps']}"
            )

        except Exception as error:
            message = f"{url}: {error}"
            print(f"ERROR: {message}", file=sys.stderr)
            source_report["error"] = str(error)
            report["errors"].append(message)

        report["sources"].append(source_report)

    renamed_count = make_bundle_identifiers_unique(all_apps)

    if fill_sizes:
        report["remoteSizesUpdated"] = fill_missing_sizes(all_apps)

    apps_with_final_size = 0
    apps_without_final_size = 0

    for app in all_apps:
        size = parse_size(app.get("size"))

        if size > 0:
            apps_with_final_size += 1
        else:
            apps_without_final_size += 1
            app["size"] = 0

        versions = app.get("versions")

        if isinstance(versions, list) and versions and isinstance(versions[0], dict):
            version_size = parse_size(versions[0].get("size"))

            if version_size <= 0:
                versions[0]["size"] = app["size"]

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
    report["appsWithFinalSize"] = apps_with_final_size
    report["appsWithoutFinalSize"] = apps_without_final_size

    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lite merged KiraStore source.")
    parser.add_argument("--output", default="dist/kirastore-index.json", help="Output JSON path")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON. This increases file size.")
    parser.add_argument(
        "--fill-missing-sizes",
        action="store_true",
        help="Fetch real IPA sizes when source size is missing or zero.",
    )

    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data, report = build_index(fill_sizes=args.fill_missing_sizes)

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
    print(f"Apps with source size: {report.get('appsWithSourceSize', 0)}")
    print(f"Apps without source size: {report.get('appsWithoutSourceSize', 0)}")
    print(f"Remote sizes updated: {report.get('remoteSizesUpdated', 0)}")
    print(f"Apps with final size: {report.get('appsWithFinalSize', 0)}")
    print(f"Apps without final size: {report.get('appsWithoutFinalSize', 0)}")

    if report.get("errors"):
        print("\nSome sources failed, but the merged source was still generated.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
