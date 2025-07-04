from ninja import Router
from ninja_jwt.authentication import JWTAuth
from .schema import RegisterSchema, MessageSchema
from .models import User
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError

router = Router(auth=JWTAuth()) 