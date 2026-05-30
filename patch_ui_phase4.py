#!/usr/bin/env python3
"""Phase 4 UI patch script for base_dashboard.html"""
import re

path = "banaaiq/templates/dashboard/base_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# ── 1. Add body_class block so the dashboard hides public navbar ──────────────
if "block body_class" not in content:
    content = "{% block body_class %}is-dashboard{% endblock %}\n" + content

# ── 2. Wrap translator link in site_engineer check ────────────────────────────
old_translator = (
    '            <a\n'
    '                id="nav-translator"\n'
    '                class="{{ \'active\' if active_dashboard == \'translator\' else \'\' }}"\n'
    '                href="{{ url_for(\'dashboard_translator\') }}"\n'
    '            ><i class="fas fa-language"></i> <span>{{ tr(\'Translator\', \'المترجم\') }}</span></a>'
)
new_translator = (
    '            {% if current_user.is_authenticated and current_user.role == \'site_engineer\' %}\n'
    '            <a\n'
    '                id="nav-translator"\n'
    '                class="{{ \'active\' if active_dashboard == \'translator\' else \'\' }}"\n'
    '                href="{{ url_for(\'dashboard_translator\') }}"\n'
    '            ><i class="fas fa-language"></i> <span>{{ tr(\'Translator\', \'المترجم\') }}</span></a>\n'
    '            {% endif %}'
)
if old_translator in content:
    content = content.replace(old_translator, new_translator)
    print("Patched: translator link wrapped in SE check (sidebar)")
else:
    # Check if already wrapped
    if "site_engineer" in content and "nav-translator" in content:
        print("Translator link already wrapped.")
    else:
        print("WARNING: could not find translator link to wrap!")

# ── 3. Wrap tutorials link in site_engineer check ─────────────────────────────
old_tutorials = (
    '            <a class="{{ \'active\' if active_dashboard == \'tutorials\' else \'\' }}"'
    ' href="{{ url_for(\'tutorials\') }}"><i class="fas fa-graduation-cap"></i>'
    ' <span>{{ tr(\'Tutorials\', \'الدروس\') }}</span></a>'
)
new_tutorials = (
    '            {% if current_user.is_authenticated and current_user.role == \'site_engineer\' %}\n'
    '            <a class="{{ \'active\' if active_dashboard == \'tutorials\' else \'\' }}"'
    ' href="{{ url_for(\'tutorials\') }}"><i class="fas fa-graduation-cap"></i>'
    ' <span>{{ tr(\'Tutorials\', \'الدروس\') }}</span></a>\n'
    '            {% endif %}'
)
if old_tutorials in content:
    content = content.replace(old_tutorials, new_tutorials)
    print("Patched: tutorials link wrapped in SE check (sidebar)")
else:
    print("WARNING: could not find tutorials link to wrap! Trying fallback...")
    # Try to find via regex
    m = re.search(
        r"(<a class=\"\{\{.*?tutorials.*?</a>)",
        content,
        re.DOTALL
    )
    if m:
        print(f"Found via regex: {m.group(0)[:80]!r}")
    else:
        print("Not found via regex either.")

# ── 4. Wrap translator in mobile bottom nav in SE check ───────────────────────
old_mobile_translator = (
    '		            <a\n'
    '		                href="{{ url_for(\'dashboard_translator\') }}"\n'
    '		                class="mobile-nav-item {% if active_dashboard == \'translator\' or (request.endpoint and \'translator\' in request.endpoint) %}active{% endif %}"\n'
    '		            >\n'
    '		                <i class="fas fa-language"></i>\n'
    '		                <span>Translate</span>\n'
    '		            </a>'
)
new_mobile_translator = (
    '		            {% if current_user.is_authenticated and current_user.role == \'site_engineer\' %}\n'
    '		            <a\n'
    '		                href="{{ url_for(\'dashboard_translator\') }}"\n'
    '		                class="mobile-nav-item {% if active_dashboard == \'translator\' or (request.endpoint and \'translator\' in request.endpoint) %}active{% endif %}"\n'
    '		            >\n'
    '		                <i class="fas fa-language"></i>\n'
    '		                <span>Translate</span>\n'
    '		            </a>\n'
    '		            {% endif %}'
)
if old_mobile_translator in content:
    content = content.replace(old_mobile_translator, new_mobile_translator)
    print("Patched: mobile translator wrapped in SE check")
else:
    print("WARNING: could not find mobile translator nav item (may already be patched or different whitespace)")

# ── 5. Wrap tutorials in mobile drawer in SE check ────────────────────────────
old_mobile_tutorials = (
    '		                <a href="{{ url_for(\'tutorials\') }}" class="mobile-drawer-link" data-bs-dismiss="offcanvas">\n'
    '		                    <i class="fas fa-graduation-cap"></i>\n'
    '		                    Tutorials\n'
    '                </a>'
)
new_mobile_tutorials = (
    '		                {% if current_user.is_authenticated and current_user.role == \'site_engineer\' %}\n'
    '		                <a href="{{ url_for(\'tutorials\') }}" class="mobile-drawer-link" data-bs-dismiss="offcanvas">\n'
    '		                    <i class="fas fa-graduation-cap"></i>\n'
    '		                    Tutorials\n'
    '                </a>\n'
    '		                {% endif %}'
)
if old_mobile_tutorials in content:
    content = content.replace(old_mobile_tutorials, new_mobile_tutorials)
    print("Patched: mobile tutorials wrapped in SE check")
else:
    print("WARNING: could not find mobile tutorials drawer item (may already be patched)")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done patching base_dashboard.html")
