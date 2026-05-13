"""One-off: fix templates with class=\\'...\\' broken Tailwind attributes."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "templates"


def main() -> None:
    fixed: list[str] = []
    for path in ROOT.rglob("*.html"):
        t = path.read_text(encoding="utf-8")
        orig = t
        # Escaped single quotes (older broken export)
        if "class=\\'" in t:
            t = re.sub(r"class=\\'([^\\']*)\\'", r'class="\1"', t)
        # Literal class='...' (invalid in Tailwind pipelines that expect double quotes)
        if "class='" in t:
            t = re.sub(r"class='([^']*)'", r'class="\1"', t)
        if t == orig:
            continue
        t = re.sub(
            r"<thead class='bg-gray-50' class=\"px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider\">",
            '<thead class="bg-gray-50">',
            t,
        )
        # parents/form duplicate classes: keep first attribute block only
        t = re.sub(
            r'(class="[^"]+") class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider"',
            r"\1",
            t,
        )
        t = re.sub(
            r'(class="[^"]+") class="px-6 py-4 whitespace-nowrap text-sm text-gray-700"',
            r"\1",
            t,
        )
        path.write_text(t, encoding="utf-8")
        fixed.append(str(path.relative_to(ROOT)))
    print(f"fixed {len(fixed)} files")
    for f in sorted(fixed):
        print(f)


if __name__ == "__main__":
    main()
