from django.shortcuts import render

# Create your views here.
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, smart_str

from .models import CustomUser as User
from .serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    # Create a new user
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.create_user(
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],  # Make sure to save email
                password=serializer.validated_data['password'],
            )
            # Do something with the user object if needed, like sending a welcome email

            return Response(
                {"message": "User created successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EmailVerifyView(APIView):
    def post(self, request):
        email = request.data.get('email')
        print(f"Received email: {email}")
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://localhost:8000/email/verify/{token}/{uid}/'
            
            print(f"User found: {user}")
            # Send email
            send_mail('Email Verification', f'Verification link: {verification_link}', settings.EMAIL_HOST_USER, [email]) 
            return Response({"message": "Verification email sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                
class EmailVerifyTokenView(APIView):
    def get(self, request, token, uid):
        
        if uid is None:
            return Response({"error": "UID is missing from request"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decode the UID
            uid = smart_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid)
            if default_token_generator.check_token(user, token):
                user.is_verified = True
                user.save()
                return Response({"message": "Email verified successfully"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"error": "User does not exist or token is invalid"}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            send_mail('Password Reset', f'Your token is {token}', 'from_email@example.com', [email])
            return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        try:
            uid = request.data.get('uid')
            user = User.objects.get(pk=urlsafe_base64_decode(uid))
            if default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)

class UserRoleView(APIView):
    def put(self, request, id):
        try:
            user = User.objects.get(pk=id)
            role = request.data.get('role')
            user.role = role  # Assume you have a `role` field in your User model
            user.save()
            return Response({"message": "Role updated successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
