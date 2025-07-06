from ninja import Router, Query

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from .schema import DoctorCreateSchema, DoctorOutSchema, DoctorCreateResponseSchema
from .schema import PatientCreateSchema, PatientOutSchema, PatientUpdateSchema
from .schema import MessageSchema
from .schema import AppointmentOutSchema, AppointmentCreateSchema, AppointmentUpdateSchema
from .models import User, Doctor, Patient, Appointment
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ninja.pagination import paginate
from typing import List

from decimal import Decimal
from datetime import datetime, date
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

appointment_router = Router(auth=JWTAuth(), tags=['Appointments'])

@appointment_router.post("/", response=AppointmentOutSchema)
def create_appointment(request, payload: AppointmentCreateSchema):
    is_admin_or_doctor(request)

    user = request.auth


    # Validate patient and doctor exist
    patient = get_object_or_404(Patient, id=payload.patient_id)
    doctor = get_object_or_404(Doctor, id=payload.doctor_id)

    # Ensure doctors only create appointments for themselves
    if user.role == "doctor" and doctor.id != user.doctor.id:
        raise HttpError(403, "Doctors can only create appointments for themselves.")
    
    # Validate date_time and appointment_cost

    if payload.appointment_cost <= Decimal("0"):
        raise HttpError(400, "Appointment cost must be greater than zero.")
    
    if payload.date_time <= timezone.now():
        raise HttpError(400, "Appointment date and time must be in the future.")    
    
    # Check if doctor already has an appointment at the same time
    if Appointment.objects.filter(
        doctor=doctor, 
        date_time=payload.date_time, 
        status=Appointment.STATUS_SCHEDULED
        ).exists():
        raise HttpError(400, "Doctor is already booked at this time")
    

    with transaction.atomic():
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            date_time=payload.date_time,
            reason=payload.reason,
            appointment_cost=payload.appointment_cost,
            status=Appointment.STATUS_SCHEDULED
            )
        return appointment
    

@appointment_router.get("/", response=List[AppointmentOutSchema])
@paginate
def list_appointments(request, 
                      date: str | None = None,
                      patient_id: int | None = None,
                      doctor_id: int | None = None,
                      status: str | None = None):
    is_admin_or_doctor(request)
    user = request.auth

    #Base Queryset
    queryset = Appointment.objects.select_related("patient", "doctor").all()

    #Restrict doctors to their own appointments
    if user.role == "doctor":
        queryset = queryset.filter(doctor_id=user.doctor.id)

        if doctor_id is not None:
            raise HttpError(403, "Doctors can only view their own appointments")
    
    #filter by patient_id
    if patient_id:
        get_object_or_404(Patient, id=patient_id)
        queryset = queryset.filter(patient_id=patient_id)

    #filter by date
    if date:
        try:
            appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
            queryset = queryset.filter(date_time__date=appointment_date)
        except ValueError:
            raise HttpError(400, "Invalid date format. Use YYYY-MM-DD.")
    
    #Filter by doctor_id (admin only)   
    if doctor_id and user.role == "admin":
        get_object_or_404(Doctor, id=doctor_id)
        queryset = queryset.filter(doctor_id=doctor_id)

    #Filter by status
    if status:
        valid_statuses = {
            Appointment.STATUS_SCHEDULED,
            Appointment.STATUS_COMPLETED,
            Appointment.STATUS_CANCELED,
        }
        if status not in valid_statuses:
            raise HttpError(400, f"Invalid status. Valid options are: {', '.join(valid_statuses)}")
        queryset = queryset.filter(status=status)
    
    
    return queryset    






@appointment_router.get("/{appointment_id}/", response=AppointmentOutSchema)
def get_appointment(request, appointment_id: int):
    is_admin_or_doctor(request)
    user = request.auth

    # Get the appointment
    appointment = get_object_or_404(
         Appointment.objects.select_related("patient", "doctor"), 
         id=appointment_id)

    # Ensure doctors only access their own appointments
    if user.role == "doctor" and appointment.doctor_id != user.doctor.id:
        raise HttpError(403, "You are not authorized to view this appointment.")
    
    return appointment


@appointment_router.put("/{appointment_id}/", response=AppointmentOutSchema)
def update_appointment(request, appointment_id: int, payload: AppointmentUpdateSchema):
    is_admin_or_doctor(request)
    user = request.auth

    # Get the appointment
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "doctor"), 
        id=appointment_id)

    # Ensure doctors only update their own appointments
    if user.role == "doctor" and appointment.doctor_id != user.doctor.id:
        raise HttpError(403, "You are not authorized to update this appointment.")
    
    # Only admin can update patient_id and doctor_id
    if payload.doctor_id and user.role != "admin":
        raise HttpError(403, "Only admins can reassign doctors.")
    if payload.patient_id and user.role != "admin":
        raise HttpError(403, "Only admins can reassign patients.")
    
    # Validate patient and doctor exist if provided
    if payload.patient_id:
        get_object_or_404(Patient, id=payload.patient_id)
        appointment.patient_id = payload.patient_id
    if payload.doctor_id:
        get_object_or_404(Doctor, id=payload.doctor_id)
        appointment.doctor_id = payload.doctor_id
    
    # Validate appointment_cost
    if payload.appointment_cost is not None and payload.appointment_cost <= Decimal("0"):
        raise HttpError(400, "Appointment cost must be greater than zero.")
    
    # Validate date_time
    if payload.date_time:
        if payload.date_time <= timezone.now():
            raise HttpError(400, "Appointment date and time must be in the future.")
    
        # Prevent double booking
        if Appointment.objects.filter(
            doctor=appointment.doctor,
            date_time=payload.date_time,
            status=Appointment.STATUS_SCHEDULED
        ).exclude(id=appointment.id).exists():
            raise HttpError(400, "Doctor already has an appointment at this time.")
        
        appointment.date_time = payload.date_time

    # Update other fields if available
    if payload.reason is not None:
        appointment.reason = payload.reason
    
    if payload.status is not None:
        valid_statuses = {
            Appointment.STATUS_SCHEDULED,
            Appointment.STATUS_COMPLETED,
            Appointment.STATUS_CANCELED,
        }
        if payload.status not in valid_statuses:
            raise HttpError(400, f"Invalid status. Valid options are: {', '.join(valid_statuses)}")
        appointment.status = payload.status
    
    if payload.appointment_cost is not None:
        appointment.appointment_cost = payload.appointment_cost


    appointment.save()
    return appointment




@appointment_router.delete("/{appointment_id}/", response=MessageSchema)
def cancel_appointment(request, appointment_id: int):
    is_admin_or_doctor(request)
    user = request.auth

    # retrieve the appointment
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "doctor"), 
        id=appointment_id)
    
    # Ensure doctors only cancel their own appointments
    if user.role == "doctor" and appointment.doctor_id != user.doctor.id:
        raise HttpError(403, "You are not authorized to cancel this appointment.")
    
    # Check if appointment is already canceled
    if appointment.status == Appointment.STATUS_CANCELED:
        raise HttpError(400, "Appointment is already canceled.")
    
    with transaction.atomic():
        appointment.status = Appointment.STATUS_CANCELED
        appointment.save()
        return MessageSchema(message="Appointment canceled successfully")
