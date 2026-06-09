from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import FormSubmission
from .serializers import FormSubmissionSerializer

@api_view(['GET', 'POST'])
def forms(request):
    if request.method == 'GET':
        qs = FormSubmission.objects.filter(owner=request.user).order_by('-created_at')
        return Response(FormSubmissionSerializer(qs, many=True).data)
    serializer = FormSubmissionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    submission = serializer.save(owner=request.user)
    return Response(FormSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
