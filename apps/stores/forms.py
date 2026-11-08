from django import forms

from apps.departments import models as DepartmentModels
from apps.stores import models as StoreModels


class DateInput(forms.DateInput):
    input_type = "date"


class BatchChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, batch):
        expiry = f", expires {batch.expiry_date:%d %b %Y}" if batch.expiry_date else ""
        return f"{batch.drug.name}: {batch.quantity_remaining} left{expiry} (batch {batch.pk})"


class StockAdjustmentForm(forms.Form):
    batch = BatchChoiceField(queryset=DepartmentModels.StockBatch.objects.none(), label="Batch")
    counted = forms.IntegerField(min_value=0, label="Units counted now",
                                 help_text="The number physically on the shelf. The difference is recorded as the adjustment.")
    reason = forms.ChoiceField(choices=StoreModels.StockAdjustment.ReasonChoices)
    notes = forms.CharField(max_length=256, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = DepartmentModels.StockBatch.objects.filter(
            quantity_remaining__gt=0).select_related("drug").order_by("drug__name", "expiry_date")

    def clean(self):
        cleaned = super().clean()
        batch, counted = cleaned.get("batch"), cleaned.get("counted")
        if batch is not None and counted is not None and counted == batch.quantity_remaining:
            self.add_error("counted", "The count matches the record; there is nothing to adjust.")
        if batch is not None and counted is not None and counted > batch.quantity_remaining and cleaned.get("reason") != "count":
            self.add_error("reason", "Only a stock count correction can raise a batch's count.")
        return cleaned


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = StoreModels.PurchaseOrder
        fields = ("supplier", "expected_on", "notes")
        widgets = {"expected_on": DateInput, "notes": forms.Textarea(attrs={"rows": 2})}


class OrderLineForm(forms.ModelForm):
    class Meta:
        model = StoreModels.PurchaseOrderLine
        fields = ("drug", "quantity_ordered", "unit_cost")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drug"].queryset = DepartmentModels.Drug.objects.filter(is_active=True)
        self.fields["quantity_ordered"].min_value = 1
        self.fields["quantity_ordered"].widget.attrs["min"] = 1
        self.fields["unit_cost"].widget.attrs["min"] = 0


OrderLineFormSet = forms.inlineformset_factory(
    StoreModels.PurchaseOrder, StoreModels.PurchaseOrderLine, form=OrderLineForm, extra=4, can_delete=False, min_num=1, validate_min=True)


class RequisitionForm(forms.ModelForm):
    class Meta:
        model = StoreModels.Requisition
        fields = ("department", "notes")


class RequisitionLineForm(forms.ModelForm):
    class Meta:
        model = StoreModels.RequisitionLine
        fields = ("drug", "quantity_requested")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drug"].queryset = DepartmentModels.Drug.objects.filter(is_active=True)
        self.fields["quantity_requested"].min_value = 1
        self.fields["quantity_requested"].widget.attrs["min"] = 1


RequisitionLineFormSet = forms.inlineformset_factory(
    StoreModels.Requisition, StoreModels.RequisitionLine, form=RequisitionLineForm, extra=4, can_delete=False, min_num=1, validate_min=True)
