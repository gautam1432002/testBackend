from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet


class SiteSettings(models.Model):
    id = models.PositiveIntegerField(primary_key=True, default=1)
    # Brand & Identity
    brand_name = models.CharField(max_length=255, default='TAARUNYAM')
    site_name = models.CharField(max_length=255, default='TAARUNYAM Platform')
    logo_url = models.URLField(blank=True)
    
    # Hero/Landing Section
    event_year = models.CharField(max_length=4, default='2026')
    main_title = models.CharField(max_length=255, default='TAARUNYAM 2026')
    subtitle = models.CharField(max_length=255, default='The Ultimate Tech Championship')
    hero_description = models.TextField(blank=True, default='Experience the synergy of innovation and competition.')
    event_date_text = models.CharField(max_length=255, default='March 2026')
    venue_text = models.CharField(max_length=255, default='University Campus')
    categories_text = models.CharField(max_length=255, default='Coding • Robotics • Design')
    countdown_date = models.DateTimeField(null=True, blank=True)
    
    # Global Contact & Footer
    contact_email = models.EmailField(default='noreply@taarunyam.com')
    footer_text = models.TextField(blank=True, default='© TAARUNYAM 2026. All rights reserved.')
    primary_color = models.CharField(max_length=20, default='#2563eb')
    
    # Nested Data (Footer/Contact structures)
    footer_json = models.JSONField(default=dict, blank=True)
    contact_json = models.JSONField(default=dict, blank=True)

    # SMTP configuration
    smtp_host = models.CharField(max_length=255, default='smtp.gmail.com')
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=512, blank=True)

    # Certificate Settings JSON (stores visual template structure from React)
    cert_settings = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'site_settings'
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1  # Singleton constraint
        # Encrypt the password if it's new/changed and not already encrypted
        if self.smtp_password and not self.smtp_password.startswith('gAAAAA'):
            fernet = Fernet(settings.FERNET_KEY)
            self.smtp_password = fernet.encrypt(self.smtp_password.encode()).decode()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Site Settings ({self.site_name})"
