from celery import shared_task
from .utils import send_email_notification, send_sms

@shared_task(bind=True, max_retries=3)
def send_email_async(self, subject, message, recipient_list):
    try:
        send_email_notification(subject, message, recipient_list)
    except Exception as e:
        self.retry(exc=e, countdown=5)  # Retry after 5 seconds, up to 3 times

@shared_task(bind=True, max_retries=3)
def send_sms_async(self, to, message):
    try:
        send_sms(to, message)
    except Exception as e:
        self.retry(exc=e, countdown=5)