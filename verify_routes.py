#!/usr/bin/env python
"""
Verify template URL references against every URL resolver used by EduManage.

The project serves tenant and public schemas from different URLconfs and uses
Django namespaces for self-contained modules. This verifier mirrors Django's
reverse-name semantics so valid ``namespace:name`` references and public-site
routes are not reported as false positives.
"""
import os
import re
from pathlib import Path


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
PUBLIC_URLCONF = "config.public_urls"


def find_templates():
    return sorted(TEMPLATES_DIR.rglob("*.html"))


def extract_url_references(template_path):
    content = template_path.read_text(encoding="utf-8")
    return re.findall(r"{%\s*url\s+[\"']([^\"']+)[\"']", content)


def _collect_url_names(resolver, namespace_prefix=""):
    names = set()
    for entry in resolver.url_patterns:
        if isinstance(entry, URLPattern):
            if entry.name:
                names.add(f"{namespace_prefix}{entry.name}")
            continue
        if not isinstance(entry, URLResolver):
            continue
        child_prefix = namespace_prefix
        if entry.namespace:
            child_prefix = f"{namespace_prefix}{entry.namespace}:"
        names.update(_collect_url_names(entry, child_prefix))
    return names


def resolver_url_names():
    """Return reverse names from tenant/local and public-schema URLconfs."""
    urlconfs = [settings.ROOT_URLCONF]
    if PUBLIC_URLCONF not in urlconfs:
        urlconfs.append(PUBLIC_URLCONF)
    names = set()
    for urlconf in urlconfs:
        names.update(_collect_url_names(get_resolver(urlconf)))
    return names


def main():
    django.setup()

    print("=" * 80)
    print("ROUTE VERIFICATION REPORT")
    print("=" * 80)

    print("\n1. Active Django URL Resolvers:")
    print("-" * 80)
    url_names = resolver_url_names()
    print(f"  URL names available across tenant/public URLconfs: {len(url_names)}")

    print("\n2. Template URL References:")
    print("-" * 80)
    templates = find_templates()
    refs_by_name = {}
    total_refs = 0
    for template in templates:
        refs = extract_url_references(template)
        total_refs += len(refs)
        for ref in refs:
            refs_by_name.setdefault(ref, []).append(template.relative_to(BASE_DIR))
        if refs:
            print(f"  OK {template.relative_to(BASE_DIR)} ({len(refs)} URL refs)")

    referenced_names = set(refs_by_name)
    missing = sorted(referenced_names - url_names)
    unused = sorted(url_names - referenced_names)

    print("\n3. Verification:")
    print("-" * 80)
    if missing:
        print(f"  FAIL: {len(missing)} broken template URL references:")
        for ref in missing:
            first_seen = refs_by_name[ref][0]
            print(f"    - {ref} first seen in {first_seen}")
    else:
        print("  PASS: All template URL references resolve.")

    if unused:
        print(f"\n  INFO: {len(unused)} URL names are not referenced in templates.")
        print("  This is normal for API endpoints, redirects, and form actions built in Python.")
        for name in unused[:20]:
            print(f"    - {name}")
        if len(unused) > 20:
            print(f"    ... and {len(unused) - 20} more")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Templates found: {len(templates)}")
    print(f"  Template URL references: {total_refs}")
    print(f"  Unique referenced URL names: {len(referenced_names)}")
    print(f"  Resolver URL names: {len(url_names)}")
    print(f"  Broken references: {len(missing)}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
