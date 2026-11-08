from rest_framework import serializers
from apps.patients import models as PatientModals
from apps.manager import models as ManagerModels
from apps.doctor import models as DoctorModels
from apps.finance import models as FinanceModels
from apps.departments import models as DepartmentModels


def user_display_name(user):
    if user is None:
        return None
    staff = getattr(user, "staff", None)
    if staff is not None:
        return staff.getFullName()
    return user.get_full_name() or user.get_username()


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientModals.Patient
        fields = "__all__"
        read_only_fields = ("patient_id", "slug", "created_on", "updated_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["fullname"] = instance.getFullName()
        representation["visit"] = PatientModals.Visit.active.filter(patient=instance).exists()
        return representation

class PatientNokSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Patient.objects.all())

    class Meta:
        model = PatientModals.NextOfKin
        fields = "__all__"
        read_only_fields = ("slug", "created_on", "updated_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["fullname"] = instance.getFullName()
        return representation

class VisitCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagerModels.VisitCategory
        fields = "__all__"

class VisitSerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Patient.objects.all())
    billing_type = serializers.PrimaryKeyRelatedField(
        queryset=FinanceModels.BillingType.objects.filter(is_active=True), write_only=True, required=False, allow_null=True)
    insurance_company = serializers.PrimaryKeyRelatedField(
        queryset=FinanceModels.InsuranceCompany.objects.filter(is_active=True), write_only=True, required=False, allow_null=True)
    account_company = serializers.PrimaryKeyRelatedField(
        queryset=FinanceModels.AccountCompany.objects.filter(is_active=True), write_only=True, required=False, allow_null=True)

    class Meta:
        model = PatientModals.Visit
        fields = "__all__"
        read_only_fields = ("visit_id", "billing", "created_on", "updated_on")

    BILLING_FIELDS = ("billing_type", "insurance_company", "account_company")

    def validate(self, attrs):
        billing_type = attrs.get("billing_type")
        if billing_type is not None:
            if billing_type.kind == "insurance" and not attrs.get("insurance_company"):
                raise serializers.ValidationError({"insurance_company": "Select the insurance company."})
            if billing_type.kind == "account" and not attrs.get("account_company"):
                raise serializers.ValidationError({"account_company": "Select the account company."})
        return attrs

    def save_billing(self, visit, billing_data):
        if not billing_data.get("billing_type"):
            return
        billing_type = billing_data["billing_type"]
        billing = visit.billing or FinanceModels.Billing()
        billing.btype = billing_type
        billing.insurance_company = billing_data.get("insurance_company") if billing_type.kind == "insurance" else None
        billing.account_company = billing_data.get("account_company") if billing_type.kind == "account" else None
        billing.save()
        if visit.billing_id != billing.id:
            visit.billing = billing
            visit.save(update_fields=["billing"])

    def create(self, validated_data):
        billing_data = {field: validated_data.pop(field, None) for field in self.BILLING_FIELDS}
        visit = super().create(validated_data)
        self.save_billing(visit, billing_data)
        return visit

    def update(self, instance, validated_data):
        billing_data = {field: validated_data.pop(field, None) for field in self.BILLING_FIELDS}
        visit = super().update(instance, validated_data)
        self.save_billing(visit, billing_data)
        return visit

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["patient"] = PatientSerializer(instance.patient).data
        representation["category"] = VisitCategorySerializer(instance.category).data
        representation["Doctor"] = str(instance.doctor) if instance.doctor else None
        speciality = instance.speciality or (instance.doctor.speciality.first() if instance.doctor else None)
        representation["Speciality"] = speciality.name if speciality else None
        billing = instance.billing
        representation["billing_type"] = billing.btype_id if billing else None
        representation["insurance_company"] = billing.insurance_company_id if billing else None
        representation["account_company"] = billing.account_company_id if billing else None
        representation["billing_label"] = str(billing) if billing else None
        return representation


class TriageSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())

    class Meta:
        model = PatientModals.Triage
        fields = "__all__"
        read_only_fields = ("created_on", "updated_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["patient"] = PatientSerializer(instance.visit.patient).data
        return representation


class AllergySerializer(serializers.ModelSerializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Patient.objects.all())

    class Meta:
        model = PatientModals.Allergy
        fields = "__all__"
        read_only_fields = ("created_on", "updated_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["patient"] = PatientSerializer(instance.patient).data
        return representation


class GeneralFindingsSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())

    class Meta:
        model = PatientModals.GeneralFinding
        fields = "__all__"
        read_only_fields = ("created_on", "updated_on")



class PaedeatricNoteSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())

    class Meta:
        model = PatientModals.PaedeatricNote
        fields = "__all__"
        read_only_fields = ("created_on", "updated_on")

class GynNoteSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())

    class Meta:
        model = PatientModals.GynNote
        fields = "__all__"
        read_only_fields = ("created_on", "updated_on")


class DiagnosisSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())

    class Meta:
        model = PatientModals.Diagnosis
        fields = "__all__"
        read_only_fields = ("created_by", "created_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["created_by"] = user_display_name(instance.created_by)
        return representation


class DrugSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentModels.Drug
        fields = ("id", "drug_number", "name", "category", "unit_price")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["category"] = instance.category.name
        representation["stock_available"] = instance.stock_available
        return representation


class PrescriptionSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())
    drug = serializers.PrimaryKeyRelatedField(queryset=DepartmentModels.Drug.objects.filter(is_active=True))

    class Meta:
        model = DepartmentModels.Prescription
        fields = ("id", "visit", "drug", "dosage", "duration", "quantity", "notes", "unit_price",
                  "quantity_issued", "prescribed_by", "created_on")
        read_only_fields = ("unit_price", "quantity_issued", "prescribed_by", "created_on")

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["drug_name"] = instance.drug.name
        representation["stock_available"] = instance.drug.stock_available
        representation["amount"] = str(instance.amount)
        representation["prescribed_by"] = user_display_name(instance.prescribed_by)
        return representation


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceModels.Service
        fields = ("id", "code", "name", "category", "fee")


class VisitServiceSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=FinanceModels.Service.objects.filter(is_active=True))

    class Meta:
        model = FinanceModels.VisitService
        fields = ("id", "visit", "service", "quantity", "price", "notes", "ordered_by", "created_on")
        read_only_fields = ("price", "ordered_by", "created_on")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["service_name"] = instance.service.name
        representation["category"] = instance.service.category
        representation["total"] = str(instance.total)
        representation["ordered_by"] = user_display_name(instance.ordered_by)
        return representation


class DepartmentRequestSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=FinanceModels.Service.objects.filter(is_active=True))

    class Meta:
        model = DepartmentModels.DepartmentRequest
        fields = ("id", "department", "visit", "service", "price", "narration", "status", "requested_by", "created_on",
                  "result", "reference_range", "comments", "reported_by", "reported_on")
        read_only_fields = ("price", "status", "requested_by", "created_on", "result", "reference_range", "comments",
                            "reported_by", "reported_on")

    def validate(self, attrs):
        if attrs["service"].category != attrs["department"]:
            raise serializers.ValidationError({"service": "This service is not offered by the selected department."})
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["service_name"] = instance.service.name
        representation["requested_by"] = user_display_name(instance.requested_by)
        representation["reported_by"] = user_display_name(instance.reported_by)
        return representation
