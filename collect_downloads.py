#!/usr/bin/env python3
"""Collect download statistics for Azure data-plane SDKs on NuGet."""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from dataclasses import dataclass
from typing import Iterable, List

import requests

SEARCH_URL = "https://azuresearch-usnc.nuget.org/query"
DEFAULT_OUTPUT = "azure_data_plane_downloads.html"
TAKE = 100  # Maximum page size supported by the NuGet search endpoint.


@dataclass
class Package:
    """Represents a NuGet package with download statistics."""

    id: str
    version: str
    total_downloads: int
    description: str
    project_url: str | None
    owners: tuple[str, ...]


def fetch_packages() -> List[Package]:
    """Fetch Azure data-plane packages from NuGet."""

    packages: List[Package] = []
    skip = 0

    while True:
        params = {
            "q": "Azure.",
            "prerelease": "false",
            "semVerLevel": "2.0.0",
            "take": TAKE,
            "skip": skip,
        }
        response = requests.get(SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data", [])
        if not entries:
            break

        for entry in entries:
            package_id = entry.get("id", "")
            if not package_id.startswith("Azure."):
                continue
            if package_id.startswith(("Azure.ResourceManager", "Azure.Core", "Azure.Identity")):
                continue

            packages.append(
                Package(
                    id=package_id,
                    version=entry.get("version", ""),
                    total_downloads=int(entry.get("totalDownloads", 0)),
                    description=entry.get("description", ""),
                    project_url=entry.get("projectUrl"),
                    owners=tuple(entry.get("owners") or ()),
                )
            )

        skip += TAKE
        total_hits = payload.get("totalHits")
        if total_hits is not None and skip >= total_hits:
            break

    return packages


def select_top_packages(packages: Iterable[Package], limit: int = 50) -> List[Package]:
    """Sort and select the top packages by download count."""

    sorted_packages = sorted(packages, key=lambda pkg: pkg.total_downloads, reverse=True)
    return sorted_packages[:limit]


def humanize_number(value: int) -> str:
    """Convert an integer into a human friendly string."""

    suffixes = ["", "K", "M", "B", "T"]
    if value < 1000:
        return str(value)

    magnitude = int(math.log(value, 1000))
    magnitude = min(magnitude, len(suffixes) - 1)
    scaled = value / (1000 ** magnitude)
    if scaled >= 100 or magnitude == 0:
        return f"{scaled:.0f}{suffixes[magnitude]}"
    return f"{scaled:.1f}{suffixes[magnitude]}"


def build_html(packages: List[Package]) -> str:
    """Create an HTML document showing package download statistics."""

    generated_at = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    max_downloads = packages[0].total_downloads if packages else 0

    rows = []
    for index, package in enumerate(packages, start=1):
        bar_width = 0 if max_downloads == 0 else (package.total_downloads / max_downloads) * 100
        bar_width = max(2, bar_width) if package.total_downloads > 0 else 0
        project_link = (
            f'<a href="{package.project_url}" target="_blank" rel="noopener">{package.id}</a>'
            if package.project_url
            else package.id
        )
        owners_display = ", ".join(package.owners) if package.owners else "—"
        row = (
            "<tr>"
            f"<td class='rank'>{index}</td>"
            f"<td class='package'>{project_link}<div class='description'>{package.description}</div></td>"
            f"<td class='owners'>{owners_display}</td>"
            f"<td class='downloads'>{package.total_downloads:,}<div class='bar' style='width: {bar_width:.2f}%;'></div></td>"
            f"<td class='human'>{humanize_number(package.total_downloads)}</td>"
            "</tr>"
        )
        rows.append(row)

    rows_html = "\n".join(rows) if rows else "<tr><td colspan='5'>No packages found.</td></tr>"

    return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <title>Azure Data-Plane SDK Downloads</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 2rem;
            background-color: #f5f7fa;
            color: #1f2933;
        }}
        h1 {{
            margin-bottom: 0.5rem;
        }}
        .meta {{
            margin-bottom: 1.5rem;
            color: #52606d;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #ffffff;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        th, td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #d9e2ec;
            vertical-align: top;
        }}
        th {{
            background-color: #243b53;
            color: #f0f4f8;
            text-align: left;
        }}
        tr:nth-child(even) td {{
            background-color: #f8fafc;
        }}
        td.rank {{
            width: 3rem;
            font-weight: bold;
        }}
        td.package {{
            width: 38%;
        }}
        td.package a {{
            color: #0967d2;
            text-decoration: none;
        }}
        td.package a:hover {{
            text-decoration: underline;
        }}
        td.owners {{
            width: 22%;
            font-size: 0.95rem;
            color: #334e68;
        }}
        .description {{
            margin-top: 0.35rem;
            font-size: 0.9rem;
            color: #52606d;
        }}
        td.downloads {{
            position: relative;
            width: 27%;
        }}
        td.downloads .bar {{
            margin-top: 0.4rem;
            height: 0.6rem;
            background: linear-gradient(90deg, #2bb0ed, #1f9dff);
            border-radius: 0.3rem;
        }}
        td.human {{
            width: 10%;
            font-weight: bold;
            text-align: right;
        }}
        .footer {{
            margin-top: 1rem;
            font-size: 0.85rem;
            color: #829ab1;
        }}
    </style>
</head>
<body>
    <h1>Azure Data-Plane SDK Downloads</h1>
    <div class=\"meta\">Top {len(packages)} packages by total downloads. Generated at {generated_at}.</div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Package</th>
                <th>Owners</th>
                <th>Total Downloads</th>
                <th>Human Readable</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div class=\"footer\">Source: nuget.org search API (data-plane packages only).</div>
</body>
</html>
"""


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Path to the HTML file to generate.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        packages = fetch_packages()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        print(f"Failed to fetch package data: {exc}", file=sys.stderr)
        return 1

    top_packages = select_top_packages(packages)
    html = build_html(top_packages)

    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html)

    print(f"Wrote {len(top_packages)} package entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
