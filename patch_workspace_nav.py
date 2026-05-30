"""Patch base_dashboard.html to update My Workspace link from /workspace to /my-workspace for site engineers."""
import sys

path = "templates/dashboard/base_dashboard.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = 'href="{{ url_for(\'engineer_workspace\') }}"'
new = 'href="{{ url_for(\'my_workspace\') }}"'

count = content.count(old)
if count == 0:
    print("Pattern not found, nothing changed.")
    sys.exit(0)

content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Replaced {count} occurrence(s) of engineer_workspace -> my_workspace")
