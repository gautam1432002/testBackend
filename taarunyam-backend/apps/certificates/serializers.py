from rest_framework import serializers
from .models import Certificate
from apps.participants.serializers import RegistrationSerializer


class CertificateSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source='registration.participant.full_name', read_only=True)
    event_title = serializers.CharField(source='registration.event.title', read_only=True)
    issued_by_username = serializers.CharField(source='issued_by.username', read_only=True, default='')

    class Meta:
        model = Certificate
        fields = [
            'id', 'qr_token', 'type', 'prize_position',
            'pdf_path', 'pdf_url', 'issued_at',
            'is_valid', 'participant_name', 'event_title',
            'issued_by_username'
        ]
        read_only_fields = ['id', 'qr_token', 'pdf_path', 'issued_at']


class GenerateCertificateSerializer(serializers.Serializer):
    registration_id = serializers.CharField()
    type = serializers.ChoiceField(choices=Certificate.TYPE_CHOICES)
    prize_position = serializers.CharField(required=False, allow_blank=True)


class BulkGenerateSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=Certificate.TYPE_CHOICES)
