from ninja import Schema
from datetime import datetime
from typing import Optional, List

#Admin Related Schemas

class DoctorCreateSchema(Schema):
    first_name: str
    last_name: str
    specialty: str
    email: str
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
    email: str
    phone: str
    created_at: datetime

class MessageSchema(Schema):
    message: str