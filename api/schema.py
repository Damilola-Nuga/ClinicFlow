from ninja import Schema
from datetime import datetime, date
from typing import Optional, List
from pydantic import EmailStr

#Admin Related Schemas

class DoctorCreateSchema(Schema):
    first_name: str
    last_name: str
    specialty: str
    email: EmailStr
    phone: str

class DoctorCreateResponseSchema(Schema):
    id: int
    username: str
    password: str
    

class DoctorOutSchema(Schema):
    id: int
    user_id: int  
    first_name: str
    last_name: str
    specialty: str
    email: EmailStr
    phone: str
    created_at: datetime

class MessageSchema(Schema):
    message: str


# Patients Related Schemas

class PatientCreateSchema(Schema):
    first_name: str
    last_name: str
    dob: date
    gender: str  # Will validate against GENDER_CHOICES in endpoint
    phone: str
    email: EmailStr | None = None
    address: str
    insurance_id: str | None = None

class PatientOutSchema(Schema):
    id: int
    first_name: str
    last_name: str
    dob: date
    gender: str
    phone: str
    email: EmailStr | None
    address: str
    insurance_id: str | None
    created_at: datetime

class PatientUpdateSchema(Schema):
    first_name: str | None = None
    last_name: str | None = None
    dob: date | None = None
    gender: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    insurance_id: str | None = None