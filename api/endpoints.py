from ninja import Router, Query

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from .schema import DoctorCreateSchema, DoctorOutSchema, DoctorCreateResponseSchema
from .schema import PatientCreateSchema, PatientOutSchema, PatientUpdateSchema
from .schema import MessageSchema
from .models import User, Doctor, Patient
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ninja.pagination import paginate
from typing import List


import secrets
import string

# Doctor endpoints (admin-only)


doctor_router = Router(auth=JWTAuth(), tags=['Doctors'])


def is_admin(request):
    if not request.auth or request.auth.role != "admin":
        raise HttpError(403, "Admin access required")
    

@doctor_router.post("/", response=DoctorCreateResponseSchema)
def create_doctor(request, payload: DoctorCreateSchema):
    is_admin(request)

    #check for unique email
    if User.objects.filter(email=payload.email).exists():
        raise HttpError(400, "A User with this Email already exists")

    # Create Unique Username and Password
    base_username = f"{payload.first_name.lower()}.{payload.last_name.lower()}"
    while True:
        random_digits = ''.join(secrets.choice(string.digits) for _ in range(4))
        username = f"{base_username}.{random_digits}"
        if not User.objects.filter(username=username).exists():
            break

    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))


    try:
        with transaction.atomic():
            user = User.objects.create(
                username=username,
                email=payload.email,
                role="doctor",
                password=make_password(password)
            )


            doctor = Doctor.objects.create(
                user=user,
                first_name=payload.first_name,
                last_name=payload.last_name,
                specialty=payload.specialty,
                phone=payload.phone
            )

            return DoctorCreateResponseSchema(
                id=doctor.id,
                username=user.username,
                password=password
            )
    except Exception as e:
        raise HttpError(400, f"Error creating doctor account: {str(e)}")
    



@doctor_router.get("/", response=List[DoctorOutSchema])
@paginate   
def list_doctors(request, specialty: str = Query(None), name: str = Query(None)):
    is_admin(request)
    queryset = Doctor.objects.select_related("user").all()
    if specialty:
        queryset = queryset.filter(specialty__icontains=specialty)
    if name:
        queryset = queryset.filter(
            Q(first_name__icontains=name) | Q(last_name__icontains=name)
        )    

    return [
    DoctorOutSchema(
        id=doctor.id,
        user_id=doctor.user.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        email=doctor.user.email,
        phone=doctor.phone,
        created_at=doctor.created_at
    )
    for doctor in queryset
    ]


@doctor_router.get("/{doctor_id}/", response=DoctorOutSchema)
def get_doctor(request, doctor_id: int):
    is_admin(request)
    try:
        doctor = Doctor.objects.select_related("user").get(id=doctor_id)
        return DoctorOutSchema(
            id=doctor.id,
            user_id=doctor.user.id,
            first_name=doctor.first_name,
            last_name=doctor.last_name,
            specialty=doctor.specialty,
            email=doctor.user.email,
            phone=doctor.phone,
            created_at=doctor.created_at
        )
    except Doctor.DoesNotExist:
        raise HttpError(404, "Doctor not found")

    


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



# Appointment endpoints (admin and doctor access)