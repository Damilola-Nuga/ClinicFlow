from ninja import Router, Query

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ..schema import MessageSchema
from ..schema import AppointmentOutSchema, AppointmentCreateSchema, AppointmentUpdateSchema
from ..models import Doctor, Patient, Appointment
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ninja.pagination import paginate
from typing import List

from decimal import Decimal
from datetime import datetime


def is_admin_or_doctor(request):
    role = request.auth.role
    if role not in ["admin", "doctor"]:
        raise HttpError(403, "Admin or Doctor access required")

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