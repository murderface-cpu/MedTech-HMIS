from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.api import serializers
from apps.api import lab_serializers

from apps.patients import models as PatientModals
from apps.lab import models as LabModels
from apps.finance import models as FinanceModels
from apps.departments import models as DepartmentModels
from apps.finance.billing import is_billed


class CustomListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def current_doctor(user):
    staff = getattr(user, "staff", None)
    return staff.doctor if staff is not None else None


class PatientAPIViews(generics.GenericAPIView):
    queryset = PatientModals.Patient.objects.all()
    serializer_class = serializers.PatientSerializer
    lookup_field = "patient_id"

class ApiRootView(APIView):
    """Entry point of the versioned API; the frontend reads its URL to build every request."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "version": "v1",
            "patients": reverse("api:patient_list", request=request),
            "visits": reverse("api:visit_list", request=request),
            "triage": reverse("api:triage_list", request=request),
        })


class PatientListView(generics.ListAPIView, PatientAPIViews):
    pagination_class = CustomListPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(patient_id__icontains=search) | Q(firstname__icontains=search) | Q(middlename__icontains=search)
                | Q(lastname__icontains=search) | Q(nin__icontains=search) | Q(telnumber__icontains=search)
            )
        return queryset

class PatientCreateView(generics.CreateAPIView, PatientAPIViews):
    pass

class PatientUpdateView(generics.UpdateAPIView, PatientAPIViews):
    pass

class PatientRetrieveView(generics.RetrieveAPIView, PatientAPIViews):
    pass

class NextOfKinViews(generics.GenericAPIView):
    queryset = PatientModals.NextOfKin.objects.all()
    serializer_class = serializers.PatientNokSerializer
    lookup_field = "pk"


class NextOfKinRetrieveView(generics.RetrieveAPIView, NextOfKinViews):
    """Next of kin of the patient with primary key `pk`."""
    def get(self, request, pk):
        patient = get_object_or_404(PatientModals.Patient, pk=pk)
        nok = patient.next_of_kin.first()
        if nok is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(nok).data)

class PatientNokCreateView(generics.CreateAPIView, NextOfKinViews):
    pass

class NextOfKinUpdateView(generics.UpdateAPIView, NextOfKinViews):
    pass


class VisitsViews(generics.GenericAPIView):
    queryset = PatientModals.Visit.active.select_related("patient", "category", "doctor", "speciality", "billing")
    serializer_class = serializers.VisitSerializer
    lookup_field = "pk"

class VisitsListView(generics.ListAPIView, VisitsViews):
    """Active visits. ?mine=1 keeps the visits assigned to the signed-in doctor."""
    pagination_class = CustomListPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.GET.get("mine"):
            queryset = queryset.filter(doctor=current_doctor(self.request.user)) if current_doctor(self.request.user) else queryset.none()
        return queryset

class VisitsRetrieveView(generics.RetrieveAPIView, VisitsViews):
    queryset = PatientModals.Visit.objects.all()

class VisitCreateView(generics.CreateAPIView, VisitsViews):
    def post(self, request, *args, **kwargs):
        if PatientModals.Visit.active.filter(patient__pk=request.data.get("patient")).exists():
            return Response({"detail": "This patient already has an active visit."}, status=status.HTTP_409_CONFLICT)
        return self.create(request, *args, **kwargs)

class VisitsUpdateView(generics.UpdateAPIView, VisitsViews):
    queryset = PatientModals.Visit.objects.all()

class PatientVisitListView(generics.ListAPIView, VisitsViews):
    def get(self, request, patient_id):
        patient = get_object_or_404(PatientModals.Patient, patient_id=patient_id)
        visits = PatientModals.Visit.active.filter(patient=patient)
        return Response(self.get_serializer(visits, many=True).data)

class VisitPatientListView(generics.RetrieveAPIView):
    queryset = PatientModals.Patient.objects.all()
    serializer_class = serializers.PatientSerializer

    def get(self, request, pk):
        visit = get_object_or_404(PatientModals.Visit, pk=pk)
        return Response(self.get_serializer(visit.patient).data)

class TriageViews(generics.GenericAPIView):
    queryset = PatientModals.Triage.objects.select_related("visit__patient")
    serializer_class = serializers.TriageSerializer
    lookup_field = "pk"

class TriageListView(generics.ListAPIView, TriageViews):
    pass

class TriageRetrieveView(generics.RetrieveAPIView, TriageViews):
    pass

class TriageUpdateView(generics.UpdateAPIView, TriageViews):
    pass

class TriageCreateView(generics.CreateAPIView, TriageViews):
    def post(self, request, *args, **kwargs):
        if PatientModals.Triage.objects.filter(visit__pk=request.data.get("visit")).exists():
            return Response({"detail": "This visit already has a triage record."}, status=status.HTTP_409_CONFLICT)
        return self.create(request, *args, **kwargs)

class VisitTriageListView(generics.ListAPIView, TriageViews):
    def get(self, request, pk):
        triage = get_object_or_404(PatientModals.Triage, visit__pk=pk)
        return Response(self.get_serializer(triage).data)


class PatientTriageListView(generics.ListAPIView, TriageViews):
    def get(self, request, patient_id):
        triages = self.get_queryset().filter(visit__patient__patient_id=patient_id)
        return Response(self.get_serializer(triages, many=True).data)



# allergies
class AllergyViews(generics.GenericAPIView):
    queryset = PatientModals.Allergy.objects.all()
    serializer_class = serializers.AllergySerializer
    lookup_field = "pk"

class AllergyListView(generics.ListAPIView, AllergyViews):
    pass
class AllergyRetrieveView(generics.RetrieveAPIView, AllergyViews):
    pass
class AllergyUpdateView(generics.UpdateAPIView, AllergyViews):
    pass
class AllergyCreateView(generics.CreateAPIView, AllergyViews):
    pass
class AllergyDeleteView(generics.DestroyAPIView, AllergyViews):
    pass

class PatientAllergyListView(generics.ListAPIView, AllergyViews):
    def get(self, request, patient_id):
        allergies = PatientModals.Allergy.objects.filter(patient__patient_id=patient_id)
        return Response(self.get_serializer(allergies, many=True).data)



# ------------------------------- Visit records ----------------------------------------
class VisitRecordViews(generics.GenericAPIView):
    """Shared views for records that belong to a visit (findings and notes)."""
    lookup_field = "pk"

class PatientVisitRecordListView(generics.ListAPIView):
    def get(self, request, patient_id):
        results = self.get_queryset().filter(visit__patient__patient_id=patient_id)
        return Response(self.get_serializer(results, many=True).data)

class VisitVisitRecordListView(generics.ListAPIView):
    def get(self, request, visit_id):
        results = self.get_queryset().filter(visit__id=visit_id)
        return Response(self.get_serializer(results, many=True).data)


class GeneralFindingsViews(VisitRecordViews):
    queryset = PatientModals.GeneralFinding.objects.all()
    serializer_class = serializers.GeneralFindingsSerializer

class GeneralFindingsListView(generics.ListAPIView, GeneralFindingsViews):
    pass

class GeneralFindingsRetrieveView(generics.RetrieveAPIView, GeneralFindingsViews):
    pass

class GeneralFindingsUpdateView(generics.UpdateAPIView, GeneralFindingsViews):
    pass

class GeneralFindingsCreateView(generics.CreateAPIView, GeneralFindingsViews):
    pass

class PatientGeneralFindingsListView(PatientVisitRecordListView, GeneralFindingsViews):
    pass

class VisitGeneralFindingsListView(VisitVisitRecordListView, GeneralFindingsViews):
    pass


# Paedeatrics
class PaedeatricsNoteViews(VisitRecordViews):
    queryset = PatientModals.PaedeatricNote.objects.all()
    serializer_class = serializers.PaedeatricNoteSerializer

class PaedeatricsNotesListView(generics.ListAPIView, PaedeatricsNoteViews):
    pass

class PaedeatricsNotesRetrieveView(generics.RetrieveAPIView, PaedeatricsNoteViews):
    pass

class PaedeatricsNotesUpdateView(generics.UpdateAPIView, PaedeatricsNoteViews):
    pass

class PaedeatricsNotesCreateView(generics.CreateAPIView, PaedeatricsNoteViews):
    pass

class PatientPaedeatricsNotesListView(PatientVisitRecordListView, PaedeatricsNoteViews):
    pass

class VisitPaedeatricsNotesListView(VisitVisitRecordListView, PaedeatricsNoteViews):
    pass


# Gyn
class GynNoteViews(VisitRecordViews):
    queryset = PatientModals.GynNote.objects.all()
    serializer_class = serializers.GynNoteSerializer

class GynNotesListView(generics.ListAPIView, GynNoteViews):
    pass

class GynNotesRetrieveView(generics.RetrieveAPIView, GynNoteViews):
    pass

class GynNotesUpdateView(generics.UpdateAPIView, GynNoteViews):
    pass

class GynNotesCreateView(generics.CreateAPIView, GynNoteViews):
    pass

class PatientGynNotesListView(PatientVisitRecordListView, GynNoteViews):
    pass

class VisitGynNotesListView(VisitVisitRecordListView, GynNoteViews):
    pass


# Diagnosis
class DiagnosisViews(VisitRecordViews):
    queryset = PatientModals.Diagnosis.objects.select_related("created_by")
    serializer_class = serializers.DiagnosisSerializer

class DiagnosisCreateView(generics.CreateAPIView, DiagnosisViews):
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class DiagnosisDeleteView(generics.DestroyAPIView, DiagnosisViews):
    pass

class VisitDiagnosisListView(VisitVisitRecordListView, DiagnosisViews):
    pass


# Pharmacy items ordered by the doctor
class DrugListView(generics.ListAPIView):
    serializer_class = serializers.DrugSerializer

    def get_queryset(self):
        queryset = DepartmentModels.Drug.objects.filter(is_active=True).select_related("category")
        search = self.request.GET.get("s")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

class PrescriptionViews(VisitRecordViews):
    queryset = DepartmentModels.Prescription.objects.select_related("drug", "prescribed_by")
    serializer_class = serializers.PrescriptionSerializer

class PrescriptionCreateView(generics.CreateAPIView, PrescriptionViews):
    def perform_create(self, serializer):
        serializer.save(prescribed_by=self.request.user)

class PrescriptionDeleteView(generics.DestroyAPIView, PrescriptionViews):
    def destroy(self, request, *args, **kwargs):
        prescription = self.get_object()
        if prescription.quantity_issued:
            return Response({"detail": "Drugs on this prescription were already issued by the pharmacy."}, status=status.HTTP_409_CONFLICT)
        if is_billed(f"prescription:{prescription.pk}"):
            return Response({"detail": "This prescription has already been invoiced."}, status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

class VisitPrescriptionListView(VisitVisitRecordListView, PrescriptionViews):
    pass


# Priced services ordered for a visit
class ServiceListView(generics.ListAPIView):
    serializer_class = serializers.ServiceSerializer

    def get_queryset(self):
        queryset = FinanceModels.Service.objects.filter(is_active=True)
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)
        return queryset

class VisitServiceViews(VisitRecordViews):
    queryset = FinanceModels.VisitService.objects.select_related("service", "ordered_by")
    serializer_class = serializers.VisitServiceSerializer

class VisitServiceCreateView(generics.CreateAPIView, VisitServiceViews):
    def perform_create(self, serializer):
        serializer.save(ordered_by=self.request.user)

class VisitServiceDeleteView(generics.DestroyAPIView, VisitServiceViews):
    def destroy(self, request, *args, **kwargs):
        if is_billed(f"visitservice:{self.get_object().pk}"):
            return Response({"detail": "This service has already been invoiced."}, status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

class VisitVisitServiceListView(VisitVisitRecordListView, VisitServiceViews):
    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(service__category=category)
        return queryset



# Cardiology and radiology examinations requested by the doctor
class DepartmentRequestViews(VisitRecordViews):
    queryset = DepartmentModels.DepartmentRequest.objects.select_related("service", "requested_by", "reported_by")
    serializer_class = serializers.DepartmentRequestSerializer

class DepartmentRequestCreateView(generics.CreateAPIView, DepartmentRequestViews):
    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

class DepartmentRequestDeleteView(generics.DestroyAPIView, DepartmentRequestViews):
    def destroy(self, request, *args, **kwargs):
        department_request = self.get_object()
        if department_request.status != "pending":
            return Response({"detail": "This examination has already been reported."}, status=status.HTTP_409_CONFLICT)
        if is_billed(f"deptrequest:{department_request.pk}"):
            return Response({"detail": "This examination has already been invoiced."}, status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

class VisitDepartmentRequestListView(VisitVisitRecordListView, DepartmentRequestViews):
    def get_queryset(self):
        queryset = super().get_queryset()
        department = self.request.GET.get("department")
        if department:
            queryset = queryset.filter(department=department)
        return queryset

# ------------------------------- Lab ----------------------------------------
class LabRequestViews(generics.GenericAPIView):
    queryset = LabModels.Request.objects.select_related("visit__patient", "category", "doctor")
    serializer_class = lab_serializers.LabRequestSerializer
    lookup_field = "pk"


def selected_tests(data):
    """[{test: <lab test id>, price: <price>}] from the request body, validated."""
    tests = data.get("selectedTests")
    if not isinstance(tests, list) or not tests:
        return None
    cleaned = {}
    for item in tests:
        test = LabModels.LabTest.objects.filter(pk=item.get("test")).first()
        if test is None:
            return None
        price = item.get("price")
        cleaned[test.pk] = (test, price if price not in ("", None) else None)
    return list(cleaned.values())


def sync_assigned_tests(lab_request, tests):
    for test, price in tests:
        assigned, _ = LabModels.AssignedTest.objects.get_or_create(request=lab_request, test=test, defaults={"price": price})
        if price is not None and assigned.price != price:
            assigned.price = price
            assigned.save()
    LabModels.AssignedTest.objects.filter(request=lab_request).exclude(test__in=[test for test, _ in tests]).delete()


class LabRequestListView(generics.ListAPIView, LabRequestViews):
    pass
class LabRequestRetrieveView(generics.RetrieveAPIView, LabRequestViews):
    pass
class LabRequestUpdateView(generics.UpdateAPIView, LabRequestViews):
    def patch(self, request, *args, **kwargs):
        lab_request = self.get_object()
        if lab_request.handled:
            return Response({"detail": "The laboratory has already handled this request."}, status=status.HTTP_409_CONFLICT)
        tests = selected_tests(request.data)
        if tests is None:
            return Response({"detail": "Select at least one valid test."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            sync_assigned_tests(lab_request, tests)
        return Response(self.get_serializer(lab_request).data)

class LabRequestCreateView(generics.CreateAPIView, LabRequestViews):
    def post(self, request, *args, **kwargs):
        visit = PatientModals.Visit.objects.filter(pk=request.data.get("visit_pk")).first()
        if visit is None:
            return Response({"detail": "Visit not found."}, status=status.HTTP_400_BAD_REQUEST)
        tests = selected_tests(request.data)
        if tests is None:
            return Response({"detail": "Select at least one valid test."}, status=status.HTTP_400_BAD_REQUEST)
        category = LabModels.RequestCategory.objects.filter(name__iexact=request.data.get("category") or "").first()

        with transaction.atomic():
            lab_request = LabModels.Request.objects.create(
                visit=visit,
                category=category,
                doctor=current_doctor(request.user),
            )
            sync_assigned_tests(lab_request, tests)
        return Response(self.get_serializer(lab_request).data, status=status.HTTP_201_CREATED)

class PatientLabRequestListView(generics.ListAPIView, LabRequestViews):
    def get(self, request, patient_id):
        patient = get_object_or_404(PatientModals.Patient, patient_id=patient_id)
        results = self.get_queryset().filter(visit__patient=patient)
        return Response(self.get_serializer(results, many=True).data)

class VisitLabRequestListView(generics.ListAPIView, LabRequestViews):
    def get(self, request, pk):
        results = self.get_queryset().filter(visit__id=pk)
        return Response(self.get_serializer(results, many=True).data)

class CategoryLabRequestListView(generics.ListAPIView, LabRequestViews):
    def get_queryset(self):
        return super().get_queryset().filter(category__name__iexact=self.kwargs["category"])


class LabTestViews(generics.GenericAPIView):
    queryset = LabModels.LabTest.objects.all()
    serializer_class = lab_serializers.LabTestSerializer
    lookup_field = "pk"

class LabTestListView(generics.ListAPIView, LabTestViews):
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("s")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return queryset

class LabTestRetrieveView(generics.RetrieveAPIView, LabTestViews):
    pass

class LabTestUpdateView(generics.UpdateAPIView, LabTestViews):
    pass

class LabTestCreateView(generics.CreateAPIView, LabTestViews):
    pass

class CategoryLabTestListView(LabTestListView):
    def get_queryset(self):
        return super().get_queryset().filter(category__name__iexact=self.kwargs["category"])

class RequestLabTestListView(generics.ListAPIView):
    serializer_class = lab_serializers.AssignedLabTestSerializer

    def get(self, request, pk):
        queryset = (LabModels.AssignedTest.objects.filter(request__pk=pk).select_related("test")
                    .prefetch_related("testresult_set", "parameter_results__subtest"))
        data = []
        for assigned in queryset:
            item = lab_serializers.LabTestSerializer(assigned.test).data
            result = assigned.testresult_set.order_by("-id").first()
            item.update({
                "assigned_id": assigned.id,
                "test": assigned.test_id,
                "price": assigned.price,
                "naration": assigned.naration,
                "result": result.results if result else None,
                "parameters": [
                    {
                        "name": parameter.subtest.name,
                        "result": parameter.results,
                        "units": parameter.subtest.units,
                        "range": parameter.subtest.dafault_range,
                    } for parameter in assigned.parameter_results.all()
                ],
            })
            data.append(item)
        return Response(data)
