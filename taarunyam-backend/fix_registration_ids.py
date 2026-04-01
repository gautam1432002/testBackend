import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taarunyam.settings.base")
django.setup()

from apps.participants.models import Registration

def run():
    # Fetch all registrations ordered historically
    regs = Registration.objects.all().order_by('registration_date')
    count = 1
    
    # We must be careful about unique constraints when updating in place.
    # To be safe, we temporarily append a placeholder for those changing, 
    # then set them to their clean versions.
    
    for r in regs:
        year = r.registration_date.year
        new_id = f'TAR-{year}-{count:03d}'
        
        if r.registration_id != new_id:
            # temporary change to avoid unique constraint if shifting ids
            r.registration_id = new_id + "_TEMP"
            r.save(update_fields=['registration_id'])
        
        count += 1

    count = 1
    for r in regs:
        year = r.registration_date.year
        new_id = f'TAR-{year}-{count:03d}'
        
        if r.registration_id != new_id:
            print(f"Setting cleaner ID: {new_id}")
            r.registration_id = new_id
            r.save(update_fields=['registration_id'])
        
        count += 1
            
    print(f"Fixed {len(regs)} registration IDs.")

if __name__ == '__main__':
    run()
