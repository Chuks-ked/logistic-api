# logistics/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Parcel
from .tasks import send_email_async, send_sms_async


@receiver(post_save, sender=Parcel)
def notify_parcel_update(sender, instance, update_fields, **kwargs):
    if update_fields and ('status' in update_fields or 'assigned_driver' in update_fields):
        cache.delete(instance.tracking_code)
        # Notify sender
        if instance.sender.profile.phone_number:
            sms_message = f"Your parcel {instance.tracking_code} is now {instance.status}."
            send_sms_async.delay(instance.sender.profile.phone_number, sms_message)
        send_email_async.delay(
            "Parcel Update",
            f"Your parcel {instance.tracking_code} is now {instance.status}.",
            [instance.sender.email]
        )

        # Notify recipient (if status changes)
        if 'status' in update_fields and instance.recipient_phone:
            sms_message = f"Your parcel {instance.tracking_code} is now {instance.status}."
            send_sms_async.delay(instance.recipient_phone, sms_message)

        # Notify driver (if assigned)
        if 'assigned_driver' in update_fields and instance.assigned_driver and instance.assigned_driver.phone_number:
            sms_message = f"You've been assigned parcel {instance.tracking_code}."
            send_sms_async.delay(instance.assigned_driver.phone_number, sms_message)