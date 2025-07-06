from django.shortcuts import render

# Create your views here.
from ninja import NinjaAPI
from ninja_extra import exceptions
from ninja_jwt.routers.obtain import obtain_pair_router
from ninja_jwt.routers.verify import verify_router
from ninja_jwt.routers.blacklist import blacklist_router
from .endpoints import doctor_router
from .endpoints import patient_router
from .endpoints import appointment_router

api = NinjaAPI()

api.add_router('/token', obtain_pair_router, tags=["Auth"])
api.add_router('/token/verify', verify_router, tags=["Auth"])
api.add_router('/token/blacklist', blacklist_router, tags=["Auth"])


api.add_router('/doctors', doctor_router)
api.add_router('/patients', patient_router)
api.add_router('/appointments', appointment_router)

# APIException Handler
def api_exception_handler(request, exc):
    headers = {}
    if isinstance(exc.detail, (list, dict)):
        data = exc.detail
    else:
        data = {"detail": exc.detail}

    response = api.create_response(request, data, status=exc.status_code)
    for k, v in headers.items():
        response.setdefault(k, v)
    return response

api.exception_handler(exceptions.APIException)(api_exception_handler)