from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.departments import models as DepartmentModels
from apps.manager.access import INVENTORY, LABORATORY, PHARMACY, has_module_access
from apps.manager.pages import PageView
from apps.stores import forms as StoreForms
from apps.stores import models as StoreModels


class StoresView(PageView):
    module = INVENTORY


# ------------------------------------------------------------------ adjustments

class StockAdjustmentsView(StoresView):
    template_name = "stores/adjustments.html"
    title = "Stock adjustments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("adjustment_form", StoreForms.StockAdjustmentForm(prefix="adjustment",
                                                                             initial={"batch": self.request.GET.get("batch")}))
        adjustments = StoreModels.StockAdjustment.objects.select_related("batch__drug", "adjusted_by")[:400]
        context["adjustments"] = adjustments
        context["written_off_value"] = sum((-adjustment.value for adjustment in adjustments if adjustment.quantity_change < 0), 0)
        return context

    def post_adjust(self, request, *args, **kwargs):
        form = StoreForms.StockAdjustmentForm(request.POST, prefix="adjustment")
        if not form.is_valid():
            return self.render_invalid(adjustment_form=form)
        batch, counted = form.cleaned_data["batch"], form.cleaned_data["counted"]
        try:
            adjustment = StoreModels.StockAdjustment.apply(batch, counted - batch.quantity_remaining, form.cleaned_data["reason"],
                                                           request.user, notes=form.cleaned_data["notes"])
        except ValueError as error:
            messages.error(request, str(error))
            return self.redirect_back()
        messages.success(request, f"{batch.drug.name} batch {batch.pk}: {adjustment.quantity_before} to {adjustment.quantity_after} units.")
        return self.redirect_back(tab="adjustment_history")


# ------------------------------------------------------------------ purchase orders

class PurchaseOrdersView(StoresView):
    template_name = "stores/purchase_orders.html"
    title = "Purchase orders"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("order_form", StoreForms.PurchaseOrderForm(prefix="order"))
        context.setdefault("line_formset", StoreForms.OrderLineFormSet(prefix="lines"))
        orders = StoreModels.PurchaseOrder.objects.select_related("supplier", "created_by").prefetch_related("lines")
        context.update({
            "open_orders": orders.filter(status__in=("draft", "sent", "partial")),
            "closed_orders": orders.filter(status__in=("received", "cancelled"))[:300],
        })
        return context

    def post_create(self, request, *args, **kwargs):
        form = StoreForms.PurchaseOrderForm(request.POST, prefix="order")
        formset = StoreForms.OrderLineFormSet(request.POST, prefix="lines")
        if not (form.is_valid() and formset.is_valid()):
            return self.render_invalid(order_form=form, line_formset=formset)
        with transaction.atomic():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            formset.instance = order
            formset.save()
        messages.success(request, f"{order.order_number} for {order.supplier} is saved as a draft. Send it when it is final.")
        return redirect("stores:purchase-order", pk=order.pk)


class PurchaseOrderDetailView(StoresView):
    template_name = "stores/purchase_order.html"
    title = "Purchase order"

    def get_order(self):
        return get_object_or_404(StoreModels.PurchaseOrder.objects.select_related("supplier", "created_by"), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        order = self.get_order()
        context = super().get_context_data(**kwargs)
        context.setdefault("line_form", StoreForms.OrderLineForm(prefix="line"))
        context.update({"order": order, "lines": order.lines.select_related("drug")})
        return context

    def post_add_line(self, request, *args, **kwargs):
        order = self.get_order()
        if order.status != "draft":
            messages.error(request, "Lines can only be added to a draft order.")
            return self.redirect_back()
        form = StoreForms.OrderLineForm(request.POST, prefix="line")
        if not form.is_valid():
            return self.render_invalid(line_form=form)
        line = form.save(commit=False)
        line.order = order
        line.save()
        messages.success(request, f"Added {line.quantity_ordered} of {line.drug.name}.")
        return self.redirect_back()

    def post_remove_line(self, request, *args, **kwargs):
        order = self.get_order()
        if order.status == "draft":
            order.lines.filter(pk=request.POST.get("line")).delete()
            messages.success(request, "The line has been removed.")
        return self.redirect_back()

    def post_send(self, request, *args, **kwargs):
        order = self.get_order()
        if order.status != "draft" or not order.lines.exists():
            messages.error(request, "Only a draft order with at least one line can be sent.")
            return self.redirect_back()
        order.status = "sent"
        order.sent_on = timezone.now()
        order.save(update_fields=["status", "sent_on"])
        messages.success(request, f"{order.order_number} is marked as sent to {order.supplier}. Receive the delivery here when it arrives.")
        return self.redirect_back()

    def post_cancel(self, request, *args, **kwargs):
        order = self.get_order()
        if order.status in ("received", "cancelled") or order.lines.filter(quantity_received__gt=0).exists():
            messages.error(request, "An order that has started arriving cannot be cancelled.")
            return self.redirect_back()
        order.status = "cancelled"
        order.save(update_fields=["status"])
        messages.success(request, f"{order.order_number} is cancelled.")
        return redirect("stores:purchase-orders")

    def post_receive(self, request, *args, **kwargs):
        order = self.get_order()
        if not order.is_open:
            messages.error(request, "Send the order before receiving it.")
            return self.redirect_back()
        received, errors = [], []
        with transaction.atomic():
            for line in order.lines.select_related("drug").select_for_update():
                raw = request.POST.get(f"receive_{line.pk}", "").strip()
                if not raw:
                    continue
                if not raw.isdigit() or int(raw) > line.outstanding:
                    errors.append(f"{line.drug.name}: receive between 0 and {line.outstanding}.")
                    continue
                quantity = int(raw)
                if quantity == 0:
                    continue
                expiry = parse_date(request.POST.get(f"expiry_{line.pk}", ""))
                if expiry is not None and expiry <= timezone.localdate():
                    errors.append(f"{line.drug.name}: the expiry date has already passed.")
                    continue
                DepartmentModels.StockBatch.objects.create(drug=line.drug, supplier=order.supplier, quantity_received=quantity,
                                                           expiry_date=expiry, received_by=request.user)
                line.quantity_received += quantity
                line.save(update_fields=["quantity_received"])
                received.append(f"{quantity} {line.drug.name}")
            if errors:
                transaction.set_rollback(True)
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.redirect_back()
        if not received:
            messages.error(request, "Enter the quantity delivered for at least one line.")
            return self.redirect_back()
        order.refresh_status()
        messages.success(request, f"Received into stock: {', '.join(received)}.")
        return self.redirect_back()


# ------------------------------------------------------------------ requisitions

class RequisitionsView(PageView):
    any_modules = (INVENTORY, PHARMACY, LABORATORY)
    template_name = "stores/requisitions.html"
    title = "Requisitions"

    def can_issue(self):
        return has_module_access(self.request.user, INVENTORY)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = {}
        if has_module_access(self.request.user, LABORATORY) and not has_module_access(self.request.user, PHARMACY):
            initial["department"] = "laboratory"
        elif has_module_access(self.request.user, PHARMACY):
            initial["department"] = "pharmacy"
        context.setdefault("requisition_form", StoreForms.RequisitionForm(prefix="requisition", initial=initial))
        context.setdefault("line_formset", StoreForms.RequisitionLineFormSet(prefix="lines"))
        requisitions = StoreModels.Requisition.objects.select_related("requested_by", "handled_by").prefetch_related("lines__drug")
        context.update({
            "pending": requisitions.filter(status="pending").order_by("requested_on"),
            "handled": requisitions.exclude(status="pending")[:300],
            "can_issue": self.can_issue(),
        })
        return context

    def post_create(self, request, *args, **kwargs):
        form = StoreForms.RequisitionForm(request.POST, prefix="requisition")
        formset = StoreForms.RequisitionLineFormSet(request.POST, prefix="lines")
        if not (form.is_valid() and formset.is_valid()):
            return self.render_invalid(requisition_form=form, line_formset=formset)
        with transaction.atomic():
            requisition = form.save(commit=False)
            requisition.requested_by = request.user
            requisition.save()
            formset.instance = requisition
            formset.save()
        messages.success(request, f"{requisition.requisition_number} is sent to the stores.")
        return self.redirect_back(tab="pending_requisitions")

    def post_issue(self, request, *args, **kwargs):
        if not self.can_issue():
            messages.error(request, "Issuing stock needs the Inventory module.")
            return self.redirect_back()
        requisition = get_object_or_404(StoreModels.Requisition, pk=request.POST.get("requisition"), status="pending")
        deduct = requisition.department != "pharmacy"
        issued, errors = [], []
        with transaction.atomic():
            for line in requisition.lines.select_related("drug"):
                raw = request.POST.get(f"issue_{line.pk}", "0").strip() or "0"
                if not raw.isdigit() or int(raw) > line.quantity_requested:
                    errors.append(f"{line.drug.name}: issue between 0 and {line.quantity_requested}.")
                    continue
                quantity = int(raw)
                if quantity and deduct:
                    try:
                        line.drug.issue(quantity)
                    except DepartmentModels.InsufficientStock as error:
                        errors.append(str(error))
                        continue
                line.quantity_issued = quantity
                line.save(update_fields=["quantity_issued"])
                issued.append(line)
            if errors:
                transaction.set_rollback(True)
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.redirect_back()
        complete = all(line.quantity_issued >= line.quantity_requested for line in issued)
        requisition.status = "issued" if complete else ("partial" if any(line.quantity_issued for line in issued) else "rejected")
        requisition.handled_by = request.user
        requisition.handled_on = timezone.now()
        requisition.response = request.POST.get("response", "").strip()[:256]
        requisition.save()
        messages.success(request, f"{requisition.requisition_number} is {requisition.get_status_display().lower()}.")
        return self.redirect_back()

    def post_reject(self, request, *args, **kwargs):
        if not self.can_issue():
            return self.redirect_back()
        requisition = get_object_or_404(StoreModels.Requisition, pk=request.POST.get("requisition"), status="pending")
        requisition.status = "rejected"
        requisition.handled_by = request.user
        requisition.handled_on = timezone.now()
        requisition.response = request.POST.get("response", "").strip()[:256] or "Rejected by the stores"
        requisition.save()
        messages.success(request, f"{requisition.requisition_number} is rejected.")
        return self.redirect_back()
