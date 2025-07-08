from ninja import Router

from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth
from ..schema import BillingReportSchema, PatientBreakdownSchema
from ..models import Appointment, Prescription
from django.db.models import Sum
from decimal import Decimal


def is_admin(request):
    if not request.auth or request.auth.role != "admin":
        raise HttpError(403, "Admin access required")
    

# Billing Report Endpoints (Admin Only)

billing_router = Router(auth=JWTAuth(), tags=['Billing Reports'])

@billing_router.get("/", response=BillingReportSchema)
def billing_report(
    request, 
    year: int = None, 
    month: int | None = None
):
    is_admin(request)

    if not year:
        raise HttpError(400, "Year is required.")
    
    appointments = Appointment.objects.select_related("patient").filter(status="completed", date_time__year=year)
    prescriptions = Prescription.objects.select_related("appointment__patient").filter(date_issued__year=year)

    if month:
        appointments = appointments.filter(date_time__month=month)
        prescriptions = prescriptions.filter(date_issued__month=month)

    total_appointments = appointments.count()
    total_prescriptions = prescriptions.count()
    total_appointment_cost = appointments.aggregate(total=Sum("appointment_cost"))["total"] or Decimal("0.00")
    total_prescription_cost = prescriptions.aggregate(total=Sum("prescription_cost"))["total"] or Decimal("0.00")
    total_income = total_appointment_cost + total_prescription_cost

    #Breakdown by patient

    patients = {}
    for appt in appointments:
        patient = appt.patient
        if patient.id not in patients:
            patients[patient.id] = {
                "patient_id": patient.id,
                "full_name": f"{patient.first_name} {patient.last_name}",
                "appointment_total": Decimal("0.00"),
                "prescription_total": Decimal("0.00"),
            }
        patients[patient.id]["appointment_total"] += appt.appointment_cost or Decimal("0.00")

    for pres in prescriptions:
        patient = pres.appointment.patient
        if patient.id not in patients:
            patients[patient.id] = {
                "patient_id": patient.id,
                "full_name": f"{patient.first_name} {patient.last_name}",
                "appointment_total": Decimal("0.00"),
                "prescription_total": Decimal("0.00"),
            }
        patients[patient.id]["prescription_total"] += pres.prescription_cost or Decimal("0.00")

    # Compute total amount for each patient

    breakdown = []
    for data in patients.values():
        data["total_amount"] = data["appointment_total"] + data["prescription_total"]
        breakdown.append(PatientBreakdownSchema(**data))

    return {
        "year": year,
        "month": month,
        "total_appointments": total_appointments,
        "total_prescriptions": total_prescriptions,
        "total_income": total_income,
        "breakdown_by_patient": breakdown
    }
