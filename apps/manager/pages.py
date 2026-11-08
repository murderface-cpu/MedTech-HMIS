from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.manager.access import ModuleAccessMixin


class PageView(ModuleAccessMixin, View):
    """A module page: requires access to `module`, renders `template_name` titled `title`.

    Forms on the page post a hidden `intent`; `post_<intent>` handles each one. A handler
    redirects back on success, or re-renders the page with the bound form to show its errors.
    """
    template_name = None
    title = ""

    def get_context_data(self, **kwargs):
        context = {"view_name": f"{settings.APPLICATION_NAME} - {self.title}", "page_title": self.title}
        context.update(kwargs)
        return context

    def render(self, **kwargs):
        return render(self.request, self.template_name, context=self.get_context_data(**kwargs))

    def get(self, request, *args, **kwargs):
        return self.render()

    def post(self, request, *args, **kwargs):
        handler = getattr(self, f"post_{request.POST.get('intent', '')}", None)
        if handler is None:
            return HttpResponseBadRequest("Unknown form.")
        return handler(request, *args, **kwargs)

    def render_invalid(self, **forms):
        """Show the page again with the submitted forms and their errors, on the tab they came from."""
        messages.error(self.request, "Please correct the errors below.")
        return self.render(initial_tab=self.request.POST.get("tab"), **forms)

    def redirect_back(self, tab=None, **params):
        """Redirect to this page (Post/Redirect/Get), keeping the open tab and any selection."""
        query = {key: value for key, value in params.items() if value not in (None, "")}
        tab = tab or self.request.POST.get("tab")
        if tab:
            query["tab"] = tab
        url = reverse(self.request.resolver_match.view_name, kwargs=self.request.resolver_match.kwargs)
        if query:
            url = f"{url}?{urlencode(query)}"
        return redirect(url)

    def form_errors(self, form):
        for field, errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else ""
            for error in errors:
                messages.error(self.request, f"{label}: {error}" if label else error)
