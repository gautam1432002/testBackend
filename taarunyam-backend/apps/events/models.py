import uuid
from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    CATEGORY_CHOICES = [
        ('Programming', 'Programming'),
        ('Knowledge', 'Knowledge'),
        ('Innovation', 'Innovation'),
        ('Web Development', 'Web Development'),
        ('Problem Solving', 'Problem Solving'),
        ('Artificial Intelligence', 'Artificial Intelligence'),
        ('Robotics', 'Robotics'),
        ('Design', 'Design'),
        ('Other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    icon = models.CharField(max_length=50, default='code', blank=True)
    venue = models.CharField(max_length=255, blank=True)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0, help_text='0 means unlimited')
    registration_deadline = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    banner_image = models.ImageField(upload_to='events/banners/', null=True, blank=True)
    prizes = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        'authentication.AdminUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'events'
        ordering = ['-event_date']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def participant_count(self):
        return self.registrations.count()

    @property
    def winner_count(self):
        return self.registrations.filter(
            certificate__type='winner'
        ).count()
