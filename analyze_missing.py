#!/usr/bin/env python
"""
Analyze missing templates and inaccessible features
"""
import os
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
APPS_DIR = BASE_DIR / "apps" / "tenant"
TEMPLATES_DIR = BASE_DIR / "templates"

def extract_view_functions(file_path):
    """Extract view function names from Python files"""
    views = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find all function definitions
            functions = re.findall(r'def\s+(\w+)\s*\([^)]*\):', content)
            views.extend(functions)
    except Exception as e:
        pass
    return views

def extract_render_calls(file_path):
    """Extract template names from render() calls"""
    templates = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find render() calls with template paths
            renders = re.findall(r'render\([^,]+,\s*["\']([^"\']+\.html)["\']', content)
            templates.extend(renders)
    except Exception as e:
        pass
    return templates

def find_all_views():
    """Find all view files and their functions"""
    view_files = {}
    for root, dirs, files in os.walk(APPS_DIR):
        for file in files:
            if file in ['views.py', 'admin_views.py', 'teacher_views.py', 'student_views.py', 'parent_views.py']:
                file_path = Path(root) / file
                module = str(file_path.relative_to(APPS_DIR)).replace('\\', '.').replace('/', '.').replace('.py', '')
                views = extract_view_functions(file_path)
                templates = extract_render_calls(file_path)
                view_files[str(file_path.relative_to(BASE_DIR))] = {
                    'views': views,
                    'templates': templates
                }
    return view_files

def find_all_templates():
    """Find all existing templates"""
    templates = []
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith('.html'):
                template_path = Path(root) / file
                rel_path = template_path.relative_to(TEMPLATES_DIR)
                templates.append(str(rel_path).replace('\\', '/'))
    return templates

def analyze_missing():
    print("=" * 100)
    print("MISSING TEMPLATES & INACCESSIBLE FEATURES ANALYSIS")
    print("=" * 100)
    
    # Get all views and existing templates
    view_files = find_all_views()
    existing_templates = set(find_all_templates())
    
    print(f"\nTotal view files analyzed: {len(view_files)}")
    print(f"Total existing templates: {len(existing_templates)}")
    
    # Analyze each module
    missing_by_module = defaultdict(list)
    views_without_templates = []
    
    for file_path, data in view_files.items():
        module_name = file_path.split('\\')[2] if '\\' in file_path else file_path.split('/')[2]
        
        # Check which views might need templates
        for view in data['views']:
            # Common patterns that usually need templates
            if any(keyword in view for keyword in ['create', 'edit', 'list', 'detail', 'form', 'home']):
                # Check if this view's template exists
                has_template = False
                for template in data['templates']:
                    if view in template or module_name in template:
                        has_template = True
                        break
                
                if not has_template:
                    views_without_templates.append({
                        'module': module_name,
                        'file': file_path,
                        'view': view
                    })
    
    # Group by module
    for item in views_without_templates:
        missing_by_module[item['module']].append(item['view'])
    
    # Print results
    print("\n" + "=" * 100)
    print("VIEWS LIKELY MISSING TEMPLATES")
    print("=" * 100)
    
    for module, views in sorted(missing_by_module.items()):
        if views:
            print(f"\n📦 {module.upper()}")
            print("-" * 100)
            for view in sorted(views):
                print(f"  ⚠️  {view}")
    
    # Find templates referenced but not existing
    print("\n" + "=" * 100)
    print("TEMPLATES REFERENCED IN CODE BUT NOT FOUND")
    print("=" * 100)
    
    all_referenced = set()
    for data in view_files.values():
        all_referenced.update(data['templates'])
    
    missing_templates = []
    for template in all_referenced:
        if template not in existing_templates:
            missing_templates.append(template)
    
    if missing_templates:
        for template in sorted(missing_templates):
            print(f"  ❌ {template}")
    else:
        print("  ✅ All referenced templates exist!")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"  Modules with potential missing templates: {len(missing_by_module)}")
    print(f"  Views without clear templates: {len(views_without_templates)}")
    print(f"  Referenced but missing templates: {len(missing_templates)}")
    
    return missing_by_module, missing_templates

if __name__ == "__main__":
    analyze_missing()
