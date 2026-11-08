from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect

from apps.manager.access import LABORATORY
from apps.manager.pages import PageView

from apps.lab import forms as LabForms
from apps.lab import models as LabModels


class LabModuleView(PageView):
    module = LABORATORY


class LaboratoryView(LabModuleView):
    template_name = "lab/index.html"
    title = "Laboratory"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("test_form", LabForms.LabTestForm(prefix="test"))
        context.setdefault("category_form", LabForms.TestCategoryForm(prefix="category"))
        requests = LabModels.Request.objects.select_related("visit__patient", "doctor", "category").prefetch_related("assignedtest_set__test")
        context.update({
            "pending_requests": requests.filter(handled=False),
            "handled_requests": requests.filter(handled=True)[:300],
            "tests": LabModels.LabTest.objects.select_related("category").prefetch_related("parameters").order_by("name"),
            "test_categories": LabModels.TestCategory.objects.order_by("name"),
        })
        return context

    def post_add_test(self, request, *args, **kwargs):
        form = LabForms.LabTestForm(request.POST, prefix="test")
        if not form.is_valid():
            return self.render_invalid(test_form=form)
        test = form.save()
        messages.success(request, f"{test.name} has been added. Add its parameters if it reports several values.")
        return redirect("lab:lab-test", pk=test.pk)

    def post_add_category(self, request, *args, **kwargs):
        form = LabForms.TestCategoryForm(request.POST, prefix="category")
        if not form.is_valid():
            return self.render_invalid(category_form=form)
        form.save()
        messages.success(request, f"Test category {form.instance.name} has been added.")
        return self.redirect_back()


class LabRequestView(LabModuleView):
    template_name = "lab/request.html"
    title = "Lab Request"

    def get_request(self):
        return get_object_or_404(LabModels.Request.objects.select_related("visit__patient", "doctor", "attendant"), pk=self.kwargs["pk"])

    def assigned_tests(self, lab_request):
        rows = []
        for assigned in lab_request.assignedtest_set.select_related("test").prefetch_related("test__parameters", "parameter_results"):
            result = assigned.testresult_set.order_by("-id").first()
            saved = {parameter.subtest_id: parameter.results for parameter in assigned.parameter_results.all()}
            rows.append({
                "assigned": assigned,
                "result": result.results if result else "",
                "parameters": [{"subtest": subtest, "value": saved.get(subtest.pk)} for subtest in assigned.test.parameters.all()],
            })
        return rows

    def get_context_data(self, **kwargs):
        lab_request = self.get_request()
        context = super().get_context_data(**kwargs)
        context.update({"lab_request": lab_request, "rows": self.assigned_tests(lab_request)})
        return context

    def post_save_results(self, request, *args, **kwargs):
        lab_request = self.get_request()
        errors = []
        with transaction.atomic():
            for row in self.assigned_tests(lab_request):
                assigned = row["assigned"]
                text = request.POST.get(f"result_{assigned.pk}", "").strip()
                result = assigned.testresult_set.order_by("-id").first()
                if text or result:
                    result = result or LabModels.TestResult(test=assigned)
                    result.results = text or None
                    result.save()
                for parameter in row["parameters"]:
                    subtest = parameter["subtest"]
                    raw = request.POST.get(f"parameter_{assigned.pk}_{subtest.pk}", "").strip()
                    try:
                        value = Decimal(raw) if raw else None
                    except InvalidOperation:
                        errors.append(f"{assigned.test.name} - {subtest.name}: '{raw}' is not a number.")
                        continue
                    LabModels.SubTestResult.objects.update_or_create(
                        assigned_test=assigned, subtest=subtest, defaults={"results": value})
            if errors:
                transaction.set_rollback(True)
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.redirect_back()

        if request.POST.get("handled"):
            lab_request.handled = True
            staff = getattr(request.user, "staff", None)
            if staff is not None and staff.doctor_id:
                lab_request.attendant = staff.doctor
            lab_request.save()
            messages.success(request, "Results saved and the request marked as handled; the doctor can now see them.")
            return redirect("lab:lab-home")
        messages.success(request, "Results saved.")
        return self.redirect_back()

    def post_reopen(self, request, *args, **kwargs):
        lab_request = self.get_request()
        lab_request.handled = False
        lab_request.save()
        messages.success(request, "The request has been reopened for changes.")
        return self.redirect_back()


class LabTestView(LabModuleView):
    template_name = "lab/test.html"
    title = "Lab Test"

    def get_test(self):
        return get_object_or_404(LabModels.LabTest, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        test = self.get_test()
        context = super().get_context_data(**kwargs)
        context.setdefault("test_form", LabForms.LabTestForm(instance=test))
        context.setdefault("parameter_form", LabForms.SubTestForm(prefix="parameter"))
        context.update({"test": test, "parameters": test.parameters.order_by("id")})
        return context

    def refresh_has_subtest(self, test):
        has_subtest = test.parameters.exists()
        if test.has_subtest != has_subtest:
            test.has_subtest = has_subtest
            test.save()

    def post_update_test(self, request, *args, **kwargs):
        test = self.get_test()
        form = LabForms.LabTestForm(request.POST, instance=test)
        if not form.is_valid():
            return self.render_invalid(test_form=form)
        form.save()
        messages.success(request, f"{test.name} has been updated.")
        return self.redirect_back()

    def post_add_parameter(self, request, *args, **kwargs):
        test = self.get_test()
        form = LabForms.SubTestForm(request.POST, prefix="parameter")
        if not form.is_valid():
            return self.render_invalid(parameter_form=form)
        parameter = form.save(commit=False)
        parameter.test = test
        parameter.save()
        self.refresh_has_subtest(test)
        messages.success(request, f"Parameter {parameter.name} has been added.")
        return self.redirect_back()

    def post_remove_parameter(self, request, *args, **kwargs):
        test = self.get_test()
        parameter = get_object_or_404(test.parameters, pk=request.POST.get("parameter"))
        if LabModels.SubTestResult.objects.filter(subtest=parameter, results__isnull=False).exists():
            messages.error(request, f"{parameter.name} already has results recorded and cannot be removed.")
            return self.redirect_back()
        parameter.delete()
        self.refresh_has_subtest(test)
        messages.success(request, f"Parameter {parameter.name} has been removed.")
        return self.redirect_back()


# ------------------------------------------------------------------ samples

class SampleCollectionView(LabModuleView):
    template_name = "lab/sample_collection.html"
    title = "Sample collection"

    def get_context_data(self, **kwargs):
        from django.utils import timezone

        context = super().get_context_data(**kwargs)
        requests = (LabModels.Request.objects.filter(handled=False)
                    .select_related("visit__patient", "doctor").prefetch_related("assignedtest_set__test", "assignedtest_set__samples")
                    .order_by("created_on"))
        waiting = []
        for lab_request in requests:
            outstanding = [assigned for assigned in lab_request.assignedtest_set.all()
                           if not any(sample.status != "rejected" for sample in assigned.samples.all())]
            if outstanding:
                waiting.append({"request": lab_request, "tests": outstanding})
        context.update({
            "waiting": waiting,
            "specimen_choices": LabModels.Sample.SpecimenChoices,
            "collected_today": LabModels.Sample.objects.filter(collected_on__date=timezone.localdate())
                                                      .select_related("request__visit__patient", "collected_by").prefetch_related("tests__test"),
        })
        return context

    def post_collect(self, request, *args, **kwargs):
        lab_request = get_object_or_404(LabModels.Request, pk=request.POST.get("request"), handled=False)
        specimen = request.POST.get("specimen")
        test_ids = [value for value in request.POST.getlist("tests") if value.isdigit()]
        tests = list(lab_request.assignedtest_set.filter(pk__in=test_ids))
        if specimen not in dict(LabModels.Sample.SpecimenChoices) or not tests:
            messages.error(request, "Choose the specimen and at least one test it is for.")
            return self.redirect_back()
        with transaction.atomic():
            sample = LabModels.Sample.objects.create(request=lab_request, specimen=specimen, collected_by=request.user,
                                                     notes=request.POST.get("notes", "").strip()[:256])
            sample.tests.set(tests)
        messages.success(request, f"Sample {sample.accession_number} collected from {lab_request.visit.patient}. Label the container with this number.")
        return self.redirect_back()


class SampleTrackingView(LabModuleView):
    template_name = "lab/sample_tracking.html"
    title = "Sample tracking"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        samples = LabModels.Sample.objects.select_related("request__visit__patient", "collected_by").prefetch_related("tests__test")
        context.update({
            "in_progress": samples.exclude(status__in=("completed", "rejected")).order_by("collected_on"),
            "finished": samples.filter(status__in=("completed", "rejected"))[:300],
        })
        return context

    def post_advance(self, request, *args, **kwargs):
        from django.utils import timezone

        sample = get_object_or_404(LabModels.Sample, pk=request.POST.get("sample"))
        if not sample.next_status:
            messages.error(request, "This sample is already finished.")
            return self.redirect_back()
        sample.status = sample.next_status
        if sample.status == "received_in_lab":
            sample.received_on = timezone.now()
        if sample.status == "completed":
            sample.completed_on = timezone.now()
        sample.save()
        messages.success(request, f"{sample.accession_number} is now {sample.get_status_display().lower()}.")
        return self.redirect_back()

    def post_reject(self, request, *args, **kwargs):
        from django.utils import timezone

        sample = get_object_or_404(LabModels.Sample, pk=request.POST.get("sample"))
        reason = request.POST.get("rejection_reason", "").strip()
        if not reason or sample.status in ("completed", "rejected"):
            messages.error(request, "Give the reason the sample is rejected, such as haemolysed or unlabelled.")
            return self.redirect_back()
        sample.status = "rejected"
        sample.rejection_reason = reason[:256]
        sample.completed_on = timezone.now()
        sample.save()
        messages.success(request, f"{sample.accession_number} is rejected. Its tests are back on Sample collection for a new sample.")
        return self.redirect_back()
