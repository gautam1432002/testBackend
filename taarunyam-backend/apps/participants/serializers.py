from rest_framework import serializers
from .models import Participant, Registration
from apps.events.serializers import EventMinimalSerializer


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = [
            'id', 'full_name', 'email', 'phone',
            'college', 'department', 'year_of_study', 'gender',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RegistrationSerializer(serializers.ModelSerializer):
    event = EventMinimalSerializer(read_only=True)
    event_id = serializers.UUIDField(write_only=True)
    is_winner = serializers.BooleanField(read_only=True)
    certificate_issued = serializers.BooleanField(read_only=True)
    certificate_sent_at = serializers.SerializerMethodField()
    certificate_id = serializers.SerializerMethodField()
    prize_position = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'id', 'registration_id', 'event', 'event_id',
            'registration_date', 'is_present', 'notes',
            'is_winner', 'prize_position',
            'certificate_issued', 'certificate_sent_at', 'certificate_id',
        ]
        read_only_fields = ['id', 'registration_id', 'registration_date']

    def get_certificate_sent_at(self, obj):
        return obj.certificate_sent_at

    def get_certificate_id(self, obj):
        if hasattr(obj, 'certificate'):
            return str(obj.certificate.qr_token)
        return None

    def get_prize_position(self, obj):
        if hasattr(obj, 'certificate'):
            return obj.certificate.prize_position
        return None


class FlatParticipantSerializer(serializers.ModelSerializer):
    """
    Flattened serializer that matches the React frontend's Participant interface exactly.
    Maps from the Registration+Participant+Certificate chain to a single object.
    """
    id = serializers.SerializerMethodField()
    certificateId = serializers.SerializerMethodField()
    name = serializers.CharField(source='participant.full_name')
    email = serializers.EmailField(source='participant.email')
    mobile = serializers.CharField(source='participant.phone')
    college = serializers.CharField(source='participant.college')
    course = serializers.CharField(source='participant.department')
    year = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    registeredAt = serializers.DateTimeField(source='registration_date')
    isWinner = serializers.BooleanField(source='is_winner')
    winnerEvent = serializers.SerializerMethodField()
    certificateIssued = serializers.BooleanField(source='certificate_issued')
    certificateSentAt = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'id', 'certificateId', 'name', 'email', 'mobile',
            'college', 'course', 'year', 'events',
            'registeredAt', 'isWinner', 'winnerEvent',
            'certificateIssued', 'certificateSentAt',
        ]

    def get_id(self, obj):
        return obj.registration_id

    def get_certificateId(self, obj):
        if hasattr(obj, 'certificate'):
            return str(obj.certificate.qr_token)
        return ''

    def get_year(self, obj):
        year_map = {'1st': '1st Year', '2nd': '2nd Year', '3rd': '3rd Year', '4th': '4th Year'}
        return year_map.get(obj.participant.year_of_study, obj.participant.year_of_study)

    def get_events(self, obj):
        return [obj.event.slug]

    def get_winnerEvent(self, obj):
        if obj.is_winner:
            return obj.event.slug
        return None

    def get_certificateSentAt(self, obj):
        return obj.certificate_sent_at


class PublicRegisterSerializer(serializers.Serializer):
    """Used for the public POST /api/register/ endpoint."""
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=20)
    college = serializers.CharField(max_length=255)
    course = serializers.CharField(max_length=255)
    year = serializers.ChoiceField(choices=['1st Year', '2nd Year', '3rd Year', '4th Year'])
    events = serializers.ListField(child=serializers.CharField(), min_length=1)
