"""Patch base_dashboard.html with role-aware nav."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard', 'base_dashboard.html')
content = open(path, encoding='utf-8').read()

# ── 1. Sidebar: wrap Projects/Portfolio, insert Workspace ──────────────────
old_nav = (
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'projects' else '' }}\" href=\"{{ url_for('projects_list') }}\"><i class=\"fas fa-folder-open\"></i> <span>{{ tr('Projects', '\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639') }}</span></a>\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'portfolio' else '' }}\" href=\"{{ url_for('portfolio') }}\"><i class=\"fas fa-chart-column\"></i> <span>{{ tr('Portfolio', '\u0645\u062d\u0641\u0638\u0629 \u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639') }}</span></a>\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'dpr' else '' }}\""
)
new_nav = (
    "\t\t            {% if current_user.is_authenticated and current_user.role == 'project_manager' %}\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'projects' else '' }}\" href=\"{{ url_for('projects_list') }}\"><i class=\"fas fa-folder-open\"></i> <span>{{ tr('Projects', '\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639') }}</span></a>\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'portfolio' else '' }}\" href=\"{{ url_for('portfolio') }}\"><i class=\"fas fa-chart-column\"></i> <span>{{ tr('Portfolio', '\u0645\u062d\u0641\u0638\u0629 \u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639') }}</span></a>\n"
    "\t\t            {% endif %}\n"
    "\t\t            {% if current_user.is_authenticated and current_user.role == 'site_engineer' %}\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'workspace' else '' }}\" href=\"{{ url_for('engineer_workspace') }}\"><i class=\"fas fa-hard-hat\"></i> <span>{{ tr('My Workspace', '\u0645\u0633\u0627\u062d\u0629 \u0639\u0645\u0644\u064a') }}</span></a>\n"
    "\t\t            {% endif %}\n"
    "\t\t            <a class=\"{{ 'active' if active_dashboard == 'dpr' else '' }}\""
)
assert old_nav in content, f"FAIL sidebar nav not found\n{repr(content[content.find('sidebar-nav'):content.find('sidebar-nav')+600])}"
content = content.replace(old_nav, new_nav, 1)
print("sidebar nav: OK")

# ── 2. Role badge after display_name ──────────────────────────────────────
old_badge = '<h6 class="mb-0 mt-2">{{ display_name }}</h6>'
new_badge = (
    '<h6 class="mb-0 mt-2">{{ display_name }}'
    '<span class="role-badge {{ \'pm\' if current_user.is_authenticated and current_user.role == \'project_manager\' else \'se\' }}">'
    '{{ \'PM\' if current_user.is_authenticated and current_user.role == \'project_manager\' else \'SE\' }}'
    '</span></h6>'
)
assert old_badge in content, "FAIL badge anchor not found"
content = content.replace(old_badge, new_badge, 1)
print("role badge: OK")

# ── 3. Mobile bottom nav ──────────────────────────────────────────────────
old_mob = (
    "\t\t            <a\n"
    "\t\t                href=\"{{ url_for('projects_list') }}\"\n"
    "\t\t                class=\"mobile-nav-item {% if active_dashboard == 'projects' or (request.endpoint and 'project' in request.endpoint) %}active{% endif %}\"\n"
    "\t\t            >\n"
    "\t\t                <i class=\"fas fa-folder-open\"></i>\n"
    "\t\t                <span>Projects</span>\n"
    "\t\t            </a>\n"
    "\t\t            <a\n"
    "\t\t                href=\"{{ url_for('portfolio') }}\"\n"
    "\t\t                class=\"mobile-nav-item {% if active_dashboard == 'portfolio' or (request.endpoint and request.endpoint in ['portfolio', 'portfolio_export']) %}active{% endif %}\"\n"
    "\t\t            >\n"
    "\t\t                <i class=\"fas fa-chart-column\"></i>\n"
    "\t\t                <span>Portfolio</span>\n"
    "\t\t            </a>"
)
new_mob = (
    "\t\t            {% if current_user.is_authenticated and current_user.role == 'project_manager' %}\n"
    "\t\t            <a\n"
    "\t\t                href=\"{{ url_for('projects_list') }}\"\n"
    "\t\t                class=\"mobile-nav-item {% if active_dashboard == 'projects' or (request.endpoint and 'project' in request.endpoint) %}active{% endif %}\"\n"
    "\t\t            >\n"
    "\t\t                <i class=\"fas fa-folder-open\"></i>\n"
    "\t\t                <span>Projects</span>\n"
    "\t\t            </a>\n"
    "\t\t            <a\n"
    "\t\t                href=\"{{ url_for('portfolio') }}\"\n"
    "\t\t                class=\"mobile-nav-item {% if active_dashboard == 'portfolio' or (request.endpoint and request.endpoint in ['portfolio', 'portfolio_export']) %}active{% endif %}\"\n"
    "\t\t            >\n"
    "\t\t                <i class=\"fas fa-chart-column\"></i>\n"
    "\t\t                <span>Portfolio</span>\n"
    "\t\t            </a>\n"
    "\t\t            {% endif %}\n"
    "\t\t            {% if current_user.is_authenticated and current_user.role == 'site_engineer' %}\n"
    "\t\t            <a\n"
    "\t\t                href=\"{{ url_for('engineer_workspace') }}\"\n"
    "\t\t                class=\"mobile-nav-item {% if active_dashboard == 'workspace' %}active{% endif %}\"\n"
    "\t\t            >\n"
    "\t\t                <i class=\"fas fa-hard-hat\"></i>\n"
    "\t\t                <span>Workspace</span>\n"
    "\t\t            </a>\n"
    "\t\t            {% endif %}"
)
assert old_mob in content, "FAIL mobile bottom nav not found"
content = content.replace(old_mob, new_mob, 1)
print("mobile bottom nav: OK")

# ── 4. Mobile drawer ──────────────────────────────────────────────────────
old_drawer = (
    "\t\t                <a href=\"{{ url_for('projects_list') }}\" class=\"mobile-drawer-link\" data-bs-dismiss=\"offcanvas\">\n"
    "\t\t                    <i class=\"fas fa-folder-open\"></i>\n"
    "\t\t                    Projects\n"
    "\t\t                </a>\n"
    "\t\t                <a href=\"{{ url_for('portfolio') }}\" class=\"mobile-drawer-link\" data-bs-dismiss=\"offcanvas\">\n"
    "\t\t                    <i class=\"fas fa-chart-column\"></i>\n"
    "\t\t                    Portfolio\n"
    "\t\t                </a>"
)
new_drawer = (
    "\t\t                {% if current_user.is_authenticated and current_user.role == 'project_manager' %}\n"
    "\t\t                <a href=\"{{ url_for('projects_list') }}\" class=\"mobile-drawer-link\" data-bs-dismiss=\"offcanvas\">\n"
    "\t\t                    <i class=\"fas fa-folder-open\"></i>\n"
    "\t\t                    Projects\n"
    "\t\t                </a>\n"
    "\t\t                <a href=\"{{ url_for('portfolio') }}\" class=\"mobile-drawer-link\" data-bs-dismiss=\"offcanvas\">\n"
    "\t\t                    <i class=\"fas fa-chart-column\"></i>\n"
    "\t\t                    Portfolio\n"
    "\t\t                </a>\n"
    "\t\t                {% endif %}\n"
    "\t\t                {% if current_user.is_authenticated and current_user.role == 'site_engineer' %}\n"
    "\t\t                <a href=\"{{ url_for('engineer_workspace') }}\" class=\"mobile-drawer-link\" data-bs-dismiss=\"offcanvas\">\n"
    "\t\t                    <i class=\"fas fa-hard-hat\"></i>\n"
    "\t\t                    My Workspace\n"
    "\t\t                </a>\n"
    "\t\t                {% endif %}"
)
assert old_drawer in content, "FAIL mobile drawer not found"
content = content.replace(old_drawer, new_drawer, 1)
print("mobile drawer: OK")

open(path, 'w', encoding='utf-8').write(content)
print("File written successfully.")
