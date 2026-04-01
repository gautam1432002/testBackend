from rest_framework import serializers
from .models import Event


class EventMinimalSerializer(serializers.ModelSerializer):
    """Slim serializer for nested use in registrations."""
    class Meta:
        model = Event
        fields = ['id', 'title', 'slug', 'event_date']
        read_only_fields = ['id', 'slug']


class EventSerializer(serializers.ModelSerializer):
    participant_count = serializers.SerializerMethodField()
    winner_count = serializers.SerializerMethodField()
    # Frontend-compatible aliases
    maxParticipants = serializers.IntegerField(source='capacity', required=False)
    eventDate = serializers.DateField(source='event_date')
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'category', 'icon',
            'venue', 'event_date', 'eventDate', 'start_time', 'end_time',
            'capacity', 'maxParticipants', 'registration_deadline', 'is_active', 'isActive',
            'banner_image', 'prizes',
            'participant_count', 'winner_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
        extra_kwargs = {
            'event_date': {'required': False},
        }

    def get_participant_count(self, obj):
        return obj.participant_count

    def get_winner_count(self, obj):
        return obj.winner_count

    def to_representation(self, instance):
        """Normalize prizes to always be a list of strings before sending to frontend."""
        data = super().to_representation(instance)

        prizes = data.get('prizes', [])
        if isinstance(prizes, dict):
            # Old format: {'1st': '10000', '2nd': '5000'} → ['10000', '5000']
            # Try to reconstruct prize strings from dict values
            normalized = []
            for key, val in prizes.items():
                if val:
                    # Format nicely if they look like numbers
                    try:
                        amount = int(str(val).replace(',', '').replace('₹', '').strip())
                        normalized.append(f'₹{amount:,}')
                    except (ValueError, TypeError):
                        normalized.append(str(val))
            data['prizes'] = normalized
        elif not isinstance(prizes, list):
            data['prizes'] = []

        return data

    def to_internal_value(self, data):
        """Accept camelCase from frontend and convert to snake_case."""
        mutable = dict(data)
        # Map camelCase to snake_case for write operations
        if 'maxParticipants' in mutable and 'capacity' not in mutable:
            mutable['capacity'] = mutable.pop('maxParticipants')
        if 'eventDate' in mutable and 'event_date' not in mutable:
            mutable['event_date'] = mutable.pop('eventDate')
        if 'isActive' in mutable and 'is_active' not in mutable:
            mutable['is_active'] = mutable.pop('isActive')
        # prizes: ensure it's a list of strings
        if 'prizes' in mutable:
            prizes = mutable['prizes']
            if isinstance(prizes, str):
                mutable['prizes'] = [p.strip() for p in prizes.split(',') if p.strip()]
            elif isinstance(prizes, dict):
                mutable['prizes'] = list(prizes.values())
        return super().to_internal_value(mutable)
