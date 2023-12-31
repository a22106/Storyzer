import datetime
import json
import logging
import traceback
from django.http import QueryDict
from django.shortcuts import render

# Create your views here.
from rest_framework import status, viewsets
from rest_framework.request import Request
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
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Results, User
# Predict View
from typing import Callable, Dict
from google.cloud import aiplatform
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
import numpy as np
import pandas as pd
import re
import os
from sentence_transformers import SentenceTransformer

# decorator
from django.utils.decorators import method_decorator
from .decorators import verify_user

from .serializers import UserSerializer

logging.basicConfig(level=logging.INFO, format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%d/%b/%Y %H:%M:%S')

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    # Create a new user
    @swagger_auto_schema(operation_description="Create a new user",
                         request_body=openapi.Schema(
                             type=openapi.TYPE_OBJECT,
                             properties={
                                 'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
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
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
            )
            
            jwt_serializer = TokenObtainPairSerializer(data={
                'email': serializer.validated_data['email'],
                'password': serializer.validated_data['password'],
            })
            
            if jwt_serializer.is_valid():
                access_token = str(jwt_serializer.validated_data['access'])
                refresh_token = str(jwt_serializer.validated_data['refresh'])
            else:
                jwt_token = TokenObtainPairSerializer.get_token(user)
                access_token = str(jwt_token.access_token)
                refresh_token = str(jwt_token)

            # Send email
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://{api_host}/email/verify/{token}/{uid}/'
            
            # Send email
            send_mail(subject='Email Verification', 
                      message=settings.VERIFICATION_EMAIL_TEMPLATE.format(verification_link)
                      , from_email= settings.EMAIL_HOST_USER, recipient_list=[user.email])
            
            return Response(
                {"message": "User created successfully. Please check your email to verify your account.", \
                "user": serializer.data, "refresh_token": refresh_token, "access_token": access_token},
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserDetailView(APIView):
    @method_decorator(verify_user)
    @swagger_auto_schema(
        operation_description="Get user detail",
        responses={
            200: 'User detail retrieved successfully',
            400: 'Invalid request',
            404: 'User does not exist',
        },
    )
    def get(self, request: Request):
        user_id = _get_user_id_from_auth(request)
        
        try:
            user_db = User.objects.get(id=user_id)
            is_staff = user_db.is_staff
            is_active = user_db.is_active
            is_verified = user_db.is_verified
            is_superuser = user_db.is_superuser
            created = user_db.created
            user_db.last_login = datetime.datetime.now()
            last_login = user_db.last_login

            # Update last login
            user_db.save()
            
            return Response({"username": user_db.username, "email": user_db.email, \
                             "is_staff": is_staff, "is_active": is_active, \
                             "is_verified": is_verified, "is_superuser": is_superuser, \
                             "created": created, "last_login": last_login}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)

def _get_user_id_from_auth(request: Request):
    # If the request is authenticated, request.user should be a user instance.
    user = request.user
    return getattr(user, 'id', None)

class Email():
    def __init__(self, email):
        self.email = email
        
    def send_verification_email(self, verification_link):
        send_mail(
            'Storyzer Email Verification', 
            settings.VERIFICATION_EMAIL_TEMPLATE.format(verification_link),
            settings.EMAIL_HOST_USER, 
            [self.email]
        )

class EmailVerifyView(APIView):
    @method_decorator(verify_user)
    @swagger_auto_schema(
        operation_description="Send verification email",
        responses={
            200: 'Verification email sent',
            400: 'User does not exist',
        },
    )
    def post(self, request: APIView):
        user_id = _get_user_id_from_auth(request)
        
        try:
            user = User.objects.get(id=user_id)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://{settings.API_HOST}/email/verify/{token}/{uid}/'
            
            # Send email
            Email(user.email).send_verification_email(verification_link)
            
            return Response({"message": "Verification email sent."}, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # General exception, this could be customized further
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
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
    @method_decorator(verify_user)
    def post(self, request: Request):
        user_id = _get_user_id_from_auth(request)
        try:
            user = User.objects.get(id=user_id)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_link = f'http://{settings.API_HOST}/password/reset/confirm/?token={token}&uid={uid}'
            send_mail('Password Reset', settings.VERIFICATION_EMAIL_TEMPLATE.format(verification_link), settings.EMAIL_HOST_USER, [user.email])
            return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    def post(self, request: APIView):
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

class MoviePredictionView(APIView):
    @method_decorator(verify_user)
    @swagger_auto_schema(
        operation_description="Predict movie genre",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Movie title'),
                'scenario': openapi.Schema(type=openapi.TYPE_STRING, description='Movie scenario'),
                'budget': openapi.Schema(type=openapi.TYPE_STRING, description='Movie budget'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='Movie language'),
                'runtime': openapi.Schema(type=openapi.TYPE_STRING, description='Movie runtime'),
                'genres': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING), description='Movie genres'),
            },
            required=['title', 'scenario', 'budget', 'language', 'runtime', 'genres'],
            example={
                "title": "The Avengers",
                "scenario": "When an unexpected enemy emerges and threatens global safety and security, Nick Fury, director of the international peacekeeping agency known as S.H.I.E.L.D., finds himself in need of a team to pull the world back from the brink of disaster. Spanning the globe, a daring recruitment effort begins!",
                "budget": "220000000",
                "language": "en",
                "runtime": "143",
                "genres": [
                    "Science Fiction",
                    "Action",
                    "Adventure"
                ]
            }
        ),
        responses={
            200: openapi.Response(
                description='Movie genre predicted successfully',
                examples={
                    'application/json': {
                        "revenue": 6097548,
                        "vote_average": 6.407,
                        "scenario": {
                            "pred_type": 2,
                            "type_keyword": {
                                "woman": 52,
                                "young": 44,
                                "love": 38,
                                "girl": 36,
                                "father": 33,
                                "man": 29,
                                "new": 25,
                                "daughter": 24,
                                "wife": 22,
                                "husband": 20
                            }
                        }
                    }
                }
            ),
            400: 'Invalid request',
        },
    )
    def post(self, request):
        try:
            user_id = _get_user_id_from_auth(request)
            user_db = User.objects.get(id=user_id)
        except AttributeError:
            logging.error(f"User is not authenticated. \n{traceback.format_exc()}")
            return Response({"error": "User is not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            logging.error(f"User does not exist. \n{traceback.format_exc()}")
            return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        if user_db is None:
            logging.error(f"User does not exist. user_id: {user_id}")
            
        # TODO: Input Json이 형식에 맞는 key값을 가지고 있는지 검증
        with open('storyzerapi/formats/movie_result_format.json', 'r') as f:
            movie_result_format = json.load(f)
            input_format = movie_result_format['results'][0]['input']
            input_keys = list(input_format.keys())
        
        # check if the scenario are in English. 
        # Otherwise, translate them into English using chatgpt
        title = str(request.data.get('title'))
        scenario = str(request.data.get('scenario'))
        budget = str(request.data.get('budget'))
        original_language = str(request.data.get('language'))
        runtime = str(request.data.get('runtime'))
        genres = request.data.get('genres')
        
        # Translate scenario into English
        scenario = scenario.replace('\n', ' ') # remove line breaks
        
        # TODO: scenario가 scenario가 아닌 경우 제대로 된 시나리오를 입력하라는 메시지를 출력
        scenario_classification = ChatGPT(scenario, settings.CHATGPT['system_prompt']['scenario_classification']).chatgpt_request() # 시나리오 분류
        
        scenario = ChatGPT(scenario, settings.CHATGPT['system_prompt']['translate_en'] 
                           ,model="gpt-3.5-turbo").chatgpt_request() # 영어로 번역
        
        scenario = re.sub(r'[^a-zA-Z0-9 ]', '', scenario) # remove special characters
        scenario = re.sub(r'\s+', ' ', scenario) # remove extra spaces
        scenario = scenario.strip() # remove leading and trailing spaces

        # Model
        PROJECT = settings.PROJECT
        LOCATION = settings.LOCATION
        VOTE_ENDPOINT = settings.VOTE_ENDPOINT
        REVENUE_ENDPOINT = settings.REVENUE_ENDPOINT
        CLASSIFICATION_ENDPOINT = settings.CLASSIFICATION_ENDPOINT
        CREDENTIALS = settings.CREDENTIALS

        # Prediction Service API (Vertex AI)
        def pred_scenario(project: str,
                            # endpoint_id: str,
                            location: str,
                            instances: Dict,
                            api_endpoint: str = "us-central1-aiplatform.googleapis.com",):

            scenario_type_instance = {'mimeType': 'text/plain',
                                      'content': instances['scenario']}
            potential_instance = instances['potential']
            
            client_options = {"api_endpoint": api_endpoint}
            client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
            parameters_dict = {}
            parameters = json_format.ParseDict(parameters_dict, Value())

            ## Prediction Scenario type
            scenario_type_instance = json_format.ParseDict(scenario_type_instance, Value())
            scenario_type_instance = [scenario_type_instance]

            scenario_endpoint = client.endpoint_path(project=project, location=location, endpoint=CLASSIFICATION_ENDPOINT)
            scenario_response = client.predict(endpoint=scenario_endpoint, instances=scenario_type_instance, parameters=parameters)

            pred_scenario = dict(scenario_response.predictions[0])
            top_confidence = np.argmax(pred_scenario['confidences'])
            scenario_type = pred_scenario['displayNames'][top_confidence]

            ## Prediction Revenue, Vote Average
            potential_instance['scenario_type'] = scenario_type
            potential_instance = json_format.ParseDict(potential_instance, Value())
            potential_instance = [potential_instance]

            revenue_endpoint = client.endpoint_path(project=project, location=location, endpoint=REVENUE_ENDPOINT)
            vote_average_endpoint = client.endpoint_path(project=project, location=location, endpoint=VOTE_ENDPOINT)

            revenue_response = client.predict(endpoint=revenue_endpoint, instances=potential_instance, parameters=parameters)
            vote_average_response = client.predict(endpoint=vote_average_endpoint, instances=potential_instance, parameters=parameters)

            pred_revenue = dict(revenue_response.predictions[0])['value']
            pred_vote_average = dict(vote_average_response.predictions[0])['value']


            predictions = {'revenue': pred_revenue, 
                           'vote_average': pred_vote_average,
                           'scenario':{'pred_type': int(scenario_type),
                                       'type_keyword': settings.SCENARIO_KEYWORDS[int(scenario_type)]["keywords"],
                           }
            }

            return predictions

        # Make Input Date
        columns = ['title_embed', 'budget', 'original_language', 'runtime', 
                    'genre_Action', 'genre_Adventure', 'genre_Animation', 'genre_Comedy', 'genre_Crime',
                    'genre_Documentary', 'genre_Drama', 'genre_Family', 'genre_Fantasy',
                    'genre_History', 'genre_Horror', 'genre_Music', 'genre_Mystery',
                    'genre_Romance', 'genre_Science_Fiction', 'genre_TV_Movie',
                    'genre_Thriller', 'genre_War', 'genre_Western',]        
        df = pd.DataFrame(columns=columns)

        ## title embedding
        model = SentenceTransformer('all-mpnet-base-v1')
        sentences = title
        title_embed = model.encode(sentences)

        df['title_embed'] = [title_embed]
        df['budget'] = [budget]
        df['original_language'] = [original_language]
        df['runtime'] = [runtime]
        for genre in genres:
            df['genre_'+genre] = [1]
        df.fillna(0, inplace=True)
        df = df.astype(str)

        potential_instance = df.iloc[0].to_dict()

        # Prediction
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = CREDENTIALS
        instances = {'scenario': scenario, 'potential': potential_instance}
        predictions = pred_scenario(PROJECT, LOCATION, instances)
        
        # system_prompt = """I'd like you to serve as a movie performance predictor. 
        # You will receive comprehensive input data in JSON format, 
        # including the movie's title, plot synopsis, budget, original language, runtime, genres, key cast, and director. 
        # If any important information is missing, please state your assumptions clearly. 
        # Your output should be in JSON format and contain your predictions for the movie's revenue and vote average. 
        # Provide a detailed analysis and explanation for your predictions, based on the given input data, 
        # and justify any assumptions you've made. Assume that you have never seen the movie in question before.
        # """

        with open('genre_average.json', 'r') as f:
            genre_average = json.load(f)

        system_prompt = settings.CHATGPT['system_prompt']['scenario_analysis']
        # user_prompt = "input" + json.dumps(request.data) + "\n" + "output" + json.dumps(predictions)
        user_prompt = f"{json.dumps(request.data)}, {json.dumps(predictions)}, {json.dumps(genre_average)}"
        system_prompt = system_prompt.format(title=title, scenario=scenario, revenue=predictions['revenue'], 
                                             budget=budget, vote_average=predictions['vote_average'], 
                                             genres=genres, type_keyword=predictions['scenario']['type_keyword'], 
                                             genre_average=genre_average)
        reply = ChatGPT(user_prompt, system_prompt).chatgpt_request()
        reply = reply.replace('\\', '')

        if user_id is not None:
            results = Results.objects.create(user_id=user_id, input=request.data, 
                                             output=predictions, analyze=reply, category="movie")
            results.save()
            logging.info(f"User prediction saved. user_id: {user_id}")
        else: # TODO: 유저 로그인 기능 완료 시 삭제
            results = Results.objects.create(user_id=5, input=request.data,
                                            output=predictions, analyze=reply, category="movie")
            results.save()
            logging.info(f"User prediction saved to default user. user_id: {user_id}")
        
        return Response({"input": request.data, 
                         "output": predictions, 
                         "analyze": reply, "category": "movie"
                         }, status=status.HTTP_200_OK)
        
class AverageGenresView(APIView):
    def get(self, request):
        with open('genre_average.json', 'r') as f:
            genre_average = json.load(f)
        return Response(genre_average, status=status.HTTP_200_OK)
    
class ChatGPTView(APIView):
    @swagger_auto_schema(
        operation_description="Chat with GPT-3.5-turbo",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, # Request body will be in JSON format
            properties={
                'system_prompt': openapi.Schema(type=openapi.TYPE_STRING, description='System prompt'),
                'user_prompt': openapi.Schema(type=openapi.TYPE_STRING, description='User prompt'),
            },
        ),
        responses={
            200: 'Text analyzed successfully',
            400: 'Invalid request',
        },
    )
    def post(self, request: Request):
        # if user_db is None: # TODO: 유저 로그인 검증 부분 별도의 데코레이터로 분리
        #     logging.error(f"User does not exist. user_id: {user_id}")
        #     return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        # elif not user_db.is_verified:
        #     logging.error(f"User is not verified. user_id: {user_id}")
        #     return Response({"error": "User is not verified"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # post data in json format
        system_prompt = request.data.get('system_prompt')
        user_prompt = request.data.get('user_prompt')
        
        reply = ChatGPT(user_prompt, system_prompt, model="gpt-3.5-turbo").chatgpt_request()
        
        return Response({"message": reply}, status=status.HTTP_200_OK)
    
class ChatGPT():
    # def __init__(self, user_prompt, system_prompt, model="gpt-3.5-turbo"):
    def __init__(self, user_prompt, system_prompt, model="gpt-4"):
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt
        self.model = model
        self.messages = []
        self.messages.append({"role": "system", "content": self.system_prompt})
        
    def chatgpt_request(self):
        openai.api_key = settings.OPENAI_API_KEY
        
        # Generate chat response
        self.messages.append({"role": "user", "content": self.user_prompt})
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=self.messages,
        )
        
        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        
        return reply

class ChatGPTAnalyzesView(APIView):
    @swagger_auto_schema(
        operation_description="Analyze text using chatgpt",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, # Request body will be in JSON format
            properties={
                'input': openapi.Schema(type=openapi.TYPE_STRING, description='Input'),
                'output': openapi.Schema(type=openapi.TYPE_STRING, description='Output'),
            },
        ),
        responses={
            200: 'Text analyzed successfully',
            400: 'Invalid request',
        },
    )
    def post(self, request):
        system_prompt = """I want you to act as a movie predictor.
        I will give you a movie title, scenario, budget, original language, runtime, and genres in json format.
        And I will give you the prediction result of the movie, revenue, and vote average in json format.
        Explain the prediction result of the movie, revenue, and vote average."""
        user_prompt = "input" + request.data.get('input') + "\n" + "output" + request.data.get('output')
        reply = ChatGPT(user_prompt, system_prompt).chatgpt_request()

        return Response({"message": reply}, status=status.HTTP_200_OK)

class ChatGPTTranslateView(APIView):
    @method_decorator(verify_user)
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
        system_prompt = settings.CHATGPT["system_prompt"]["translate_en"]
        user_prompt = request.data.get('context')
        
        reply = ChatGPT(user_prompt, system_prompt, model="gpt-3.5-turbo").chatgpt_request()
        
        return Response({"message": reply}, status=status.HTTP_200_OK)

class ResultSaveView(APIView):
    def create(self, request):
        pass
        
class ResultListView(APIView):
    @method_decorator(verify_user)
    @swagger_auto_schema(
        operation_description="Get results",
        manual_parameters=[
            openapi.Parameter('user_id', openapi.IN_QUERY, description="User ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('category', openapi.IN_QUERY, description="Category", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER)
        ],
        responses={
            200: 'Results retrieved successfully',
            400: 'Invalid request',
        },
    )
    def get(self, request: Request, *args, **kwargs):
        # print(request.__dict__)
        results = Results.objects.all()
        user_id = _get_user_id_from_auth(request)
        user_id = request.query_params.get('user_id') if request.query_params.get('user_id') is not None else user_id
        user_id = 0 if user_id is None else user_id
        category = request.query_params.get('category')
        page = request.query_params.get('page', 1)
        page = 1 if page is None or not page.isdigit() or int(page) < 1 else int(page)
        
        if user_id is not None:
            user_db = User.objects.filter(id=user_id).first()
            if user_db is not None:
                if user_id == 0: # load all results
                    pass
                results = results.filter(user_id=user_id)
            else:
                return Response({"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        
        if category is not None:
            results = results.filter(category=category)
            
        try:
            # 10 results per page
            results_list = []
            for result in results:
                results_list.append({"input": result.input, 
                                     "output": result.output, 
                                     "analyze": result.analyze, 
                                     "category": result.category})
            results_list = results_list[(page-1)*10:page*10] if len(results_list) >= page*10 else results_list[(page-1)*10:]
            
            response_data = {
                "page": page,
                "results": results_list,
                "totalResults": len(results_list),
                "totalPages": len(results_list) // 10 + 1,
            }
        except Exception as e:
            logging.error(f"Error occurred while getting results. error: {str(e)}")
            logging.info(f"{traceback.format_exc()}")
            return Response({"error": f"Error occurred while getting results. error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(response_data, status=status.HTTP_200_OK)