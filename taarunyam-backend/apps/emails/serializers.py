from rest_framework import serializers
from .models import EmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source='certificate.registration.participant.full_name', read_only=True)
    event_title = serializers.CharField(source='certificate.registration.event.title', read_only=True)
    certificate_type = serializers.CharField(source='certificate.type', read_only=True)
    qr_token = serializers.StringRelatedField(source='certificate.qr_token', read_only=True)

    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient_email', 'status', 'celery_task_id',
            'sent_at', 'error_message', 'retry_count', 'created_at',
            'participant_name', 'event_title', 'certificate_type', 'qr_token'
        ]
        read_only_fields = ['id', 'created_at']


class SendEmailSerializer(serializers.Serializer):
    certificate_id = serializers.UUIDField()


class BulkSendEmailSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
