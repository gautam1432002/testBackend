from rest_framework import serializers
from .models import SiteSettings


# Default structures to ensure frontend always gets complete data
_DEFAULT_FOOTER = {
    'description': 'The Ultimate Tech Championship.',
    'extraInfo': 'Organized by Tech Innovation Society.',
    'copyright': '© 2026 TAARUNYAM Tech Event. All rights reserved.',
}

_DEFAULT_CONTACT = {
    'email': 'contact@taarunyam2026.com',
    'phone': '+91 98765 43210',
    'location': 'Tech Campus, Innovation City',
}


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'brand_name', 'event_year', 'main_title', 'subtitle',
            'hero_description', 'event_date_text', 'venue_text',
            'categories_text', 'countdown_date', 'cert_settings',
            'footer_json', 'contact_json',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        """Return camelCase fields that the frontend expects."""
        footer = instance.footer_json or {}
        contact = instance.contact_json or {}
        countdown = instance.countdown_date

        return {
            # Brand
            'brandName': instance.brand_name or 'TAARUNYAM',
            'eventYear': instance.event_year or '2026',
            # Hero section
            'mainTitle': instance.main_title or 'TAARUNYAM',
            'subtitle': instance.subtitle or 'Tech Event 2026',
            'description': instance.hero_description or 'The Ultimate Tech Championship',
            'eventDate': instance.event_date_text or 'March 2026',
            'eventVenue': instance.venue_text or 'Tech Campus',
            'categoriesText': instance.categories_text or '6 Exciting Events',
            'countdownDate': countdown.isoformat() if countdown else '2026-03-15T09:00:00',
            # Footer nested object
            'footer': {
                'description': footer.get('description', _DEFAULT_FOOTER['description']),
                'extraInfo': footer.get('extraInfo', _DEFAULT_FOOTER['extraInfo']),
                'copyright': footer.get('copyright', _DEFAULT_FOOTER['copyright']),
            },
            # Contact nested object
            'contact': {
                'email': contact.get('email', _DEFAULT_CONTACT['email']),
                'phone': contact.get('phone', _DEFAULT_CONTACT['phone']),
                'location': contact.get('location', _DEFAULT_CONTACT['location']),
            },
            # Certificate template (passed through as-is)
            'certSettings': instance.cert_settings or {},
        }


class AdminSiteSettingsSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_smtp_password = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SiteSettings
        fields = [
            'brand_name', 'event_year', 'main_title', 'subtitle',
            'hero_description', 'event_date_text', 'venue_text',
            'categories_text', 'countdown_date', 'cert_settings',
            'footer_json', 'contact_json',
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
            'has_smtp_password', 'updated_at',
        ]

    def get_has_smtp_password(self, obj):
        return bool(obj.smtp_password)

    def to_representation(self, instance):
        """Return camelCase fields for the admin panel."""
        base = PublicSiteSettingsSerializer(instance).to_representation(instance)
        # Append admin-only fields
        base.update({
            'smtpHost': instance.smtp_host,
            'smtpPort': instance.smtp_port,
            'smtpUser': instance.smtp_user,
            'hasSmtpPassword': bool(instance.smtp_password),
            'updatedAt': instance.updated_at.isoformat() if instance.updated_at else None,
        })
        return base

    def to_internal_value(self, data):
        """Accept camelCase or snake_case from the frontend and normalize to model fields."""
        mutable = dict(data)

        # camelCase → snake_case translation
        mapping = {
            'brandName': 'brand_name',
            'eventYear': 'event_year',
            'mainTitle': 'main_title',
            'subtitle': 'subtitle',
            'description': 'hero_description',
            'eventDate': 'event_date_text',
            'eventVenue': 'venue_text',
            'categoriesText': 'categories_text',
            'countdownDate': 'countdown_date',
            'certSettings': 'cert_settings',
            # footer / contact nested objects
            'footer': '__footer__',
            'contact': '__contact__',
            # SMTP
            'smtpHost': 'smtp_host',
            'smtpPort': 'smtp_port',
            'smtpUser': 'smtp_user',
            'smtpPassword': 'smtp_password',
        }

        normalized = {}
        for key, value in mutable.items():
            mapped = mapping.get(key, key)
            if mapped == '__footer__':
                # Merge footer dict into footer_json
                normalized['footer_json'] = value
            elif mapped == '__contact__':
                normalized['contact_json'] = value
            else:
                normalized[mapped] = value

        return super().to_internal_value(normalized)


class SMTPTestSerializer(serializers.Serializer):
    test_email = serializers.EmailField()
