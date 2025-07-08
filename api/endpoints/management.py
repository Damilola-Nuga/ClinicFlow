from ninja import Router
from ninja.errors import HttpError
from django.contrib.auth.hashers import make_password
from ..models import User
from ninja_jwt.authentication import JWTAuth
from ninja.responses import Response
from django.core.mail import send_mail
from django.db import transaction

from ..schema import AdminCreateSchema, MessageSchema

management_router = Router(auth=JWTAuth(), tags=['Admin Management'])

def is_admin(request):
    if not request.auth or request.auth.role != "admin":
        raise HttpError(403, "Admin access required")
    
@management_router.post("/", response=MessageSchema)
def create_admin(request, payload: AdminCreateSchema):
    is_admin(request)

    username = payload.username.strip()
    email = payload.email.strip()

    # Check if user already exists
    if User.objects.filter(email=email).exists():
        raise HttpError(400, "A User with this Email already exists")
    
    if User.objects.filter(username=username).exists():
        raise HttpError(400, "A User with this Username already exists")
    
    # Validate password 
    if len(payload.password) < 6:
        raise HttpError(400, "Password must be at least 6 characters long")
    

    try:
        with transaction.atomic():
            # Create the admin user
            user = User.objects.create(
                username=payload.username,
                email=payload.email,
                role="admin",
                password=make_password(payload.password) # Ensure password is hashed in the model
            )

            # Send email with credentials

            send_mail(
                subject="Your Admin Acoount for ClinicFlow",
                message=(
                    f"Hello {user.username},\n\n"
                    "Your admin account has been created successfully.\n"
                    f"Username: {user.username}\n"
                    f"Password: {payload.password}\n\n"
                    "Please log in and change your password immediately."
                ),
                from_email="noreply@clinicflow.com",
                recipient_list=[user.email],
                fail_silently=False
            )

    except Exception as e:
        raise HttpError(400, f"Error creating doctor account: {str(e)}")
    
    return MessageSchema(message=f"Admin {user.username} created successfully.")