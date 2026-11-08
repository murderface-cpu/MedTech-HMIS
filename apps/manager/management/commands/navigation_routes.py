from django.core.management.base import BaseCommand

from apps.manager.navigation import WORKSPACES, page_url


class Command(BaseCommand):
    help = "Prints the menu as Markdown route tables for docs/design/navigation.md."

    def handle(self, *args, **options):
        for workspace in WORKSPACES:
            self.stdout.write(f"\n### {workspace.label}\n")
            self.stdout.write("| Section | Page | Route | Access | Status |")
            self.stdout.write("| --- | --- | --- | --- | --- |")
            for section in workspace.sections:
                for page in section.pages:
                    route = page.planned_route if page.planned else page_url(page)
                    access = "Staff users" if page.staff_only else ", ".join(page.modules)
                    status = "Planned" if page.planned else "Live"
                    self.stdout.write(f"| {section.label} | {page.label} | `{route}` | {access} | {status} |")
