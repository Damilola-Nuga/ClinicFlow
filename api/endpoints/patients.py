from ninja import Router

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ..schema import PatientCreateSchema, PatientOutSchema, PatientUpdateSchema
from ..schema import MessageSchema
from ..models import Patient
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja.pagination import paginate
from typing import List






# Patient endpoints (admin and doctor access)

patient_router = Router(auth=JWTAuth(), tags=['Patients'])

def is_admin_or_doctor(request):
    role = request.auth.role
    if role not in ["admin", "doctor"]:
        raise HttpError(403, "Admin or Doctor access required")
    
@patient_router.post("/", response=PatientOutSchema)
def create_patient(request, payload: PatientCreateSchema):
    is_admin_or_doctor(request)

    if payload.gender not in dict(Patient.GENDER_CHOICES):
        raise HttpError(400, "Invalid gender choice")
    
    patient = Patient.objects.create(**payload.dict())
    return patient

@patient_router.get("/", response=List[PatientOutSchema])
@paginate
def list_patients(request, name: str = None):
    is_admin_or_doctor(request)
    queryset = Patient.objects.all()
    if name:
        queryset = queryset.filter(
            Q(first_name__icontains=name) | Q(last_name__icontains=name)
        )
    return queryset 

@patient_router.get("/{patient_id}/", response=PatientOutSchema)
def get_patient(request, patient_id: int):
    is_admin_or_doctor(request)
    patient = get_object_or_404(Patient, id=patient_id)
    return patient

@patient_router.put("/{patient_id}/", response=PatientOutSchema)
def update_patient(request, patient_id: int, payload: PatientUpdateSchema):
    is_admin_or_doctor(request)
    patient = get_object_or_404(Patient, id=patient_id)

    data = payload.dict(exclude_unset=True)

    if "gender" in data and data["gender"] not in dict(Patient.GENDER_CHOICES):
        raise HttpError(400, "Invalid gender choice")
    
    for field, value in data.items():
        setattr(patient, field, value)

    patient.save()
    return patient


@patient_router.delete("/{patient_id}/", response=MessageSchema)
def delete_patient(request, patient_id: int):
    is_admin_or_doctor(request)
    patient = get_object_or_404(Patient, id=patient_id)
    patient.delete()
    return MessageSchema(message="Patient deleted successfully")