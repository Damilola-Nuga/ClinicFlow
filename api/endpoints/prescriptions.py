from ninja import Router

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ..schema import PrescriptionCreateSchema, PrescriptionOutSchema
from ..models import Appointment, Prescription
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja.pagination import paginate
from typing import List
from decimal import Decimal




def is_admin_or_doctor(request):
    role = request.auth.role
    if role not in ["admin", "doctor"]:
        raise HttpError(403, "Admin or Doctor access required")

# Prescription Enpoints (Admin and Doctor)

prescription_router = Router(auth=JWTAuth(), tags=['Prescriptions'])

@prescription_router.post("/", response=PrescriptionOutSchema)
def create_prescription(request, payload: PrescriptionCreateSchema):

    user = request.auth

    # Only Doctors can create prescriptions
    if user.role != "doctor":
        raise HttpError(403, "Only doctors can create prescriptions.")
    
    # Fetch the appoitnment and verify ownership
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor"),
        id=payload.appointment_id
    )

    if appointment.doctor_id != user.doctor.id:
        raise HttpError(403, "You are not the assigned doctor for this appointment.")
    
    # Ensure appointment is completed
    if appointment.status != Appointment.STATUS_COMPLETED:
        raise HttpError(400, "Prescriptions can only be created for completed appointments.")

    # Validate date
    if payload.date_issued < appointment.date_time.date():
        raise HttpError(400, "Prescription date cannot be before the appointment date")
    
    # Validate prescription_cost
    if payload.prescription_cost is not None and payload.prescription_cost < Decimal("0"):
        raise HttpError(400, "Prescription cost must be non-negative.")

    # Create the prescription

    with transaction.atomic():
        prescription = Prescription.objects.create(
            appointment=appointment,
            medication=payload.medication,
            dosage=payload.dosage,
            instructions=payload.instructions,
            date_issued=payload.date_issued,
            prescription_cost=payload.prescription_cost
        )
        return prescription
    

@prescription_router.get("/", response=List[PrescriptionOutSchema])
@paginate
def list_prescriptions(
    request,
    patient_id: int | None = None,
    appointment_id: int | None = None,
    doctor_id: int | None = None
):

    is_admin_or_doctor(request)
    user = request.auth

    prescriptions = Prescription.objects.select_related("appointment", "appointment__patient", "appointment__doctor")

    # Restrict to doctor's prescriptions if user is a doctor
    if user.role == "doctor":
        if doctor_id and doctor_id != user.doctor.id:
            raise HttpError(403, "Doctors can only view their own prescriptions.")
        prescriptions = prescriptions.filter(appointment__doctor_id=user.doctor.id)

    # Filter by patient_id and appointment_id if provided
    if patient_id:
        prescriptions = prescriptions.filter(appointment__patient_id=patient_id)
    if doctor_id:
        prescriptions = prescriptions.filter(appointment__doctor_id=doctor_id)
    if appointment_id:
        prescriptions = prescriptions.filter(appointment_id=appointment_id)

    return prescriptions.order_by("-date_issued")


@prescription_router.get("/{prescription_id}/", response=PrescriptionOutSchema)
def get_prescription(request, prescription_id: int):
    is_admin_or_doctor(request)
    user = request.auth

    # Fetch the prescription
    prescription = get_object_or_404(
        Prescription.objects.select_related("appointment__doctor"),
        id=prescription_id
    )

    # Ensure doctors only access their own prescriptions
    if user.role == "doctor" and prescription.appointment.doctor_id != user.doctor.id:
        raise HttpError(403, "You are not authorized to view this prescription.")
    
    return prescription