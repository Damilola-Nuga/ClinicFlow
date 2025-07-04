from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Doctor, Patient, Appointment, Prescription
# Register your models here.

admin.site.register(User, UserAdmin)  # Use the default UserAdmin for the custom User model


admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(Appointment)
admin.site.register(Prescription)