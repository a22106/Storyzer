from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request


def verify_user(fun):
    @wraps(fun)
    def wrapper(*args, **kwargs):
        request = args[0]
        user_id = _get_user_id_from_auth(request)
        if user_id is None:
            return Response({"error": "User is not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        return fun(*args, **kwargs)
    return wrapper

def _get_user_id_from_auth(request: Request):
    # If the request is authenticated, request.user should be a user instance.
    user = request.user
    return getattr(user, 'id', None)