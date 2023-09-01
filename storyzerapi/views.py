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
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from manage import api_host
import openai

from .models import CustomUser as User
from .serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    # Create a new user
    @swagger_auto_schema(operation_description="Create a new user",
                         request_body=openapi.Schema(
                             type=openapi.TYPE_OBJECT,
                             properties={
                                #  'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                                 'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email'),
                                 'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password'),
                             },
                         ),
                         responses={
                             201: 'User created successfully',
                             400: 'Invalid request',
                         },
                    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.create_user(
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],  # Make sure to save email
                password=serializer.validated_data['password'],
            )

            # Send email
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://{api_host}/email/verify/{token}/{uid}/'
            
            # Send email
            send_mail('Email Verification', settings.VERIFICATION_EMAIL_TEMPLATE.format(verification_link)
                      , settings.EMAIL_HOST_USER, [user.email])
            
            return Response(
                {"message": "User created successfully. Please check your email to verify your account."},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EmailVerifyView(APIView):
    @swagger_auto_schema(
        operation_description="Send verification email",
        responses={
            200: 'Verification email sent',
            400: 'User does not exist',
        },
    )
    def post(self, request):
        email = request.data.get('email') # User model has field `email`
        print(f"request.data: {request.data}")
        print(f"Received email: {email}")
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://{api_host}/email/verify/{token}/{uid}/'
            
            # Send email
            send_mail('Email Verification', settings.VERIFICATION_EMAIL_TEMPLATE.format(verification_link)
                      , settings.EMAIL_HOST_USER, [user.email])
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
    @swagger_auto_schema(
        operation_descript="Update user role",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'role': openapi.Schema(type=openapi.TYPE_STRING, description='New role for the user'),
            },
        ),
        responses={
            200: 'Role updated successfully',
            400: 'User does not exist',
        },
    )
        
    def put(self, request, id):
        try:
            user = User.objects.get(pk=id)
            role = request.data.get('role')
            user.role = role  # Assume you have a `role` field in your User model
            user.save()
            return Response({"message": "Role updated successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)

import re

class MoviePredictionView(APIView):
    @swagger_auto_schema(
        operation_description="Predict movie genre",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, # Request body will be in JSON format
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Movie title'),
                'scenario': openapi.Schema(type=openapi.TYPE_STRING, description='Movie scenario'),
                'budget': openapi.Schema(type=openapi.TYPE_INTEGER, description='Movie budget'),
                'original_language': openapi.Schema(type=openapi.TYPE_STRING, description='Movie original language'),
                'runtime': openapi.Schema(type=openapi.TYPE_INTEGER, description='Movie runtime'),
                'genres': openapi.Schema(type=openapi.TYPE_STRING, description='Movie genres'),
            }
        ),
        responses={ # Response code
            200: 'Movie genre predicted successfully',
            400: 'Invalid request',
        },
    )
    def post(self, request):
        # check if the scenario are in English. 
        # Otherwise, translate them into English using chatgpt
        title = request.data.get('title')
        scenario = request.data.get('scenario')
        original_language = request.data.get('original_language')
        
        # TODO: get keywords from scenario
        
        # TODO: predict the result from vertex AI tables

class ChatGPTTranslateView(APIView):
    @swagger_auto_schema(
        operation_description="Translate text using GPT-3.5-turbo",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, # Request body will be in JSON format
            properties={
                'context': openapi.Schema(type=openapi.TYPE_STRING, description='Context'),
            },
        ),
        responses={
            200: 'Text translated successfully',
            400: 'Invalid request',
        },
    )
    def post(self, request):
        # post data in json format
        
        system_prompt = """I want you to act as a translator. 
        I will give you a sentence in any other language, 
        and you will translate it into English.
        No matter what language the sentence is in, you will translate it into English.
        No need to speak descriptive sentences, just translate the sentence into English.
        """
        user_prompt = request.data.get('context')
        
        openai.api_key = settings.OPENAI_API_KEY
        
        # Generate chat response
        messages = []
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        
        reply = response.choices[0].message.content
        
        return Response({"message": reply}, status=status.HTTP_200_OK)
