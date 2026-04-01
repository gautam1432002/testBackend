from rest_framework import serializers
from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'sender_name', 'sender_email', 'subject', 'message', 'is_read', 'received_at']
        read_only_fields = ['id', 'received_at', 'is_read']


class PublicContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['sender_name', 'sender_email', 'subject', 'message']
