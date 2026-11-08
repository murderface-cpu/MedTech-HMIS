from django import forms

from apps.lab import models as LabModels


class LabTestForm(forms.ModelForm):
    class Meta:
        model = LabModels.LabTest
        fields = ("name", "category", "price", "dafault_range", "description")
        labels = {"dafault_range": "Normal range"}
        widgets = {"dafault_range": forms.Textarea(attrs={"rows": 2}), "description": forms.Textarea(attrs={"rows": 2})}

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is not None and price < 0:
            raise forms.ValidationError("Enter a price of zero or more.")
        return price


class TestCategoryForm(forms.ModelForm):
    class Meta:
        model = LabModels.TestCategory
        fields = ("name",)


class SubTestForm(forms.ModelForm):
    class Meta:
        model = LabModels.SubTest
        fields = ("name", "units", "lower_limit", "upper_limit", "normal_result", "dafault_range")
        labels = {"dafault_range": "Normal range (text)"}
        widgets = {"dafault_range": forms.TextInput()}

    def clean(self):
        cleaned = super().clean()
        lower, upper = cleaned.get("lower_limit"), cleaned.get("upper_limit")
        if lower is not None and upper is not None and lower > upper:
            self.add_error("upper_limit", "The upper limit must not be below the lower limit.")
        return cleaned
