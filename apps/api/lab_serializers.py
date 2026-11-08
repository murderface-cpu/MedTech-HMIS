from rest_framework import serializers

from apps.patients import models as PatientModals
from apps.lab import models as LabModels

from apps.api import serializers as GeneralSerializers


class LabRequestCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LabModels.RequestCategory
        fields = "__all__"

class LabRequestSerializer(serializers.ModelSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientModals.Visit.objects.all())
    class Meta:
        model = LabModels.Request
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["patient"] = GeneralSerializers.PatientSerializer(instance.visit.patient).data
        representation["visit_id"] = instance.visit.visit_id
        representation["category"] = LabRequestCategorySerializer(instance.category).data if instance.category else {"name": None}
        representation["doctor"] = str(instance.doctor) if instance.doctor else None
        return representation

class LabTestCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LabModels.TestCategory
        fields = "__all__"

class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabModels.LabTest
        fields = "__all__"

class AssignedLabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabModels.AssignedTest
        fields = "__all__"
