from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.decorators import (
    api_view, permission_classes, renderer_classes,
    )
from rest_framework.authtoken.models import Token
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404

from accounts.serializers import UserSerializer, ProfileSerializer
from accounts.models import CustomUser

# See https://studygyaan.com/django/django-rest-framework-tutorial-register-login-logout?noamp=mobile


# Below doesn't work since the GET request is empty
# class UserDetail(APIView):
#     # renderer_classes = [TemplateHTMLRenderer]
#     template_name = 'rest_framework/user_detail.html'

#     @api_view(['GET', 'POST'])
#     @renderer_classes([TemplateHTMLRenderer])
#     def as_view(self, *args, **kwargs):
#         if self.request.method == 'POST':
#             user = get_object_or_404(CustomUser, username=self.user.username)
            
#             if user:
#                 token, _ = Token.objects.get_or_create(user=user)
#                 return Response(
#                     {'token': token.key}, status=status.HTTP_200_OK
#                     )
        
        # serializer = UserSerializer(user)
        # return Response(
        #     serializer.data,
        #     template_name=self.template_name)

        # return Response(serializer.data)



# @api_view(['GET'])
# @renderer_classes([TemplateHTMLRenderer])
# def user_detail(request):
#     user = get_object_or_404(CustomUser, username=request.user.username)
#     user_serialized = UserSerializer(user)
#     return Response(user_serialized.data)

# class ProfileAPI(APIView):
#     def get(self, request, *args, **kwargs):
#         user = get_object_or_404(CustomUser, pk=kwargs['user_id'])
#         profile_serializer = ProfileSerializer(user.profile)
#         return Response(profile_serializer.data)

class UserAPI(APIView):
    """Return a user; users can only read themselves, staff can read all."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(CustomUser, pk=kwargs['user_id'])
        if user.pk != request.user.pk and not request.user.is_staff:
            raise NotFound()
        serializer = UserSerializer(user)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def register_user(request):
    if request.method == 'POST':
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'GET'])
def user_login(request):
    if request.method == 'POST':
        username = request.data.get('username')
        password = request.data.get('password')

        user = None
        if '@' in username:
            try:
                user = CustomUser.objects.get(email=username)
            except ObjectDoesNotExist:
                pass

        if not user:
            user = authenticate(username=username, password=password)

        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key}, status=status.HTTP_200_OK)

        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
            )
    # elif request.method == 'GET':
    #     renderer_classes = [TemplateHTMLRenderer]
    #     template_name = 'login.html'
    #     serializer = UserSerializer(request)
        
    #     return Response({'serializer': serializer, 'profile': serializer.get()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_logout(request):
    if request.method == 'POST':
        try:
            # Delete the user's token to logout
            request.user.auth_token.delete()
            return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class HTMLAPIView(viewsets.ViewSet):
#     renderer_classes = [TemplateHTMLRenderer]
#     template_name = 'base.html'


#     def list(self, request):
#         queryset = Hints.objects.order_by('pk')        
#         return Response({'queryset': queryset}) 