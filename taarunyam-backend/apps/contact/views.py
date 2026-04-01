from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.authentication.permissions import IsAdmin

from .models import ContactMessage
from .serializers import ContactMessageSerializer, PublicContactSerializer


def _success(data, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message}, status=status_code)


class PublicContactView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PublicContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return _success({}, 'Your message has been sent successfully. We will get back to you soon.', status.HTTP_201_CREATED)


class AdminContactListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = ContactMessage.objects.all()

        is_read_filter = request.query_params.get('is_read')
        if is_read_filter is not None:
            qs = qs.filter(is_read=is_read_filter.lower() == 'true')

        from taarunyam.pagination import StandardPagination
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ContactMessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminContactReadView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        try:
            msg = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            return Response({'success': False, 'data': {}, 'message': 'Message not found.'}, status=404)

        msg.is_read = request.data.get('is_read', True)
        msg.save()
        return _success(ContactMessageSerializer(msg).data, 'Message status updated.')
