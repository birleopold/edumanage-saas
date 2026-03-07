#!/usr/bin/env python
"""
Route Verification Script
Checks all URL patterns and templates are properly configured
"""
import os
import re
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
APPS_DIR = BASE_DIR / "apps" / "tenant"
TEMPLATES_DIR = BASE_DIR / "templates"

def find_url_patterns():
    """Find all URL pattern files"""
    url_files = []
    for root, dirs, files in os.walk(APPS_DIR):
        for file in files:
            if file.endswith('urls.py'):
                url_files.append(Path(root) / file)
    return url_files

def extract_url_names(file_path):
    """Extract URL names from a URL configuration file"""
    url_names = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find name= parameters in path() calls
            names = re.findall(r'name=["\']([^"\']+)["\']', content)
            url_names.extend(names)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return url_names

def find_templates():
    """Find all template files"""
    templates = []
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith('.html'):
                templates.append(Path(root) / file)
    return templates

def extract_url_references(template_path):
    """Extract {% url %} references from a template"""
    url_refs = []
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find {% url 'name' %} patterns
            refs = re.findall(r'{%\s*url\s+["\']([^"\']+)["\']', content)
            url_refs.extend(refs)
    except Exception as e:
        print(f"Error reading {template_path}: {e}")
    return url_refs

def main():
    print("=" * 80)
    print("ROUTE VERIFICATION REPORT")
    print("=" * 80)
    
    # 1. Find all URL patterns
    print("\n1. URL Configuration Files:")
    print("-" * 80)
    url_files = find_url_patterns()
    all_url_names = set()
    
    for url_file in sorted(url_files):
        rel_path = url_file.relative_to(BASE_DIR)
        names = extract_url_names(url_file)
        all_url_names.update(names)
        print(f"  ✓ {rel_path} ({len(names)} URLs)")
    
    print(f"\n  Total URL patterns defined: {len(all_url_names)}")
    
    # 2. Find all templates
    print("\n2. Template Files:")
    print("-" * 80)
    templates = find_templates()
    all_url_refs = set()
    
    for template in sorted(templates):
        rel_path = template.relative_to(BASE_DIR)
        refs = extract_url_references(template)
        all_url_refs.update(refs)
        if refs:
            print(f"  ✓ {rel_path} ({len(refs)} URL refs)")
    
    print(f"\n  Total templates: {len(templates)}")
    print(f"  Total unique URL references: {len(all_url_refs)}")
    
    # 3. Check for broken references
    print("\n3. Verification:")
    print("-" * 80)
    broken_refs = all_url_refs - all_url_names
    
    if broken_refs:
        print(f"  ⚠ WARNING: {len(broken_refs)} potentially broken URL references:")
        for ref in sorted(broken_refs):
            print(f"    - {ref}")
    else:
        print("  ✓ All URL references appear valid!")
    
    # 4. Unused URLs
    unused_urls = all_url_names - all_url_refs
    if unused_urls:
        print(f"\n  ℹ INFO: {len(unused_urls)} URLs not referenced in templates (may be API endpoints):")
        for url in sorted(list(unused_urls)[:20]):  # Show first 20
            print(f"    - {url}")
        if len(unused_urls) > 20:
            print(f"    ... and {len(unused_urls) - 20} more")
    
    # 5. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  URL Patterns Defined: {len(all_url_names)}")
    print(f"  Templates Found: {len(templates)}")
    print(f"  URL References in Templates: {len(all_url_refs)}")
    print(f"  Broken References: {len(broken_refs)}")
    print(f"  Unused URLs: {len(unused_urls)}")
    
    if len(broken_refs) == 0:
        print("\n  ✅ PASS: All template URL references are valid!")
        return 0
    else:
        print("\n  ❌ FAIL: Found broken URL references that need fixing!")
        return 1

if __name__ == "__main__":
    exit(main())
