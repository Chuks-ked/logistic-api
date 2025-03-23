import logging
import requests
from threading import Thread
from django.conf import settings
from django.core.mail import send_mail
from twilio.rest import Client

logger = logging.getLogger(__name__)  # Logging for errors

def send_sms(to, message):
    """
    Sends an SMS message using Twilio API.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to
        )
        logger.info(f"SMS sent to {to}")
        return True
    except Exception as e:
        logger.error(f"SMS error to {to}: {e}")
        return False
    


def get_coordinates(address):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": settings.GOOGLE_MAPS_API_KEY
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises an error for failed requests
        data = response.json()

        if data.get("status") == "OK":
            location = data["results"][0]["geometry"]["location"]
            logger.info(f"Coordinates retrieved for {address}")
            return location["lat"], location["lng"]
        else:
            logger.warning(f"No coordinates found for {address}")
            return None, None
    except requests.RequestException as e:
        logger.error(f"Google Maps API error for {address}: {e}")

    return None, None


class EmailThread(Thread):
    """
    Sends emails asynchronously using a separate thread.
    """
    def __init__(self, subject, message, recipient_list, from_email=None):
        self.subject = subject
        self.message = message
        self.recipient_list = recipient_list
        self.from_email = from_email or settings.DEFAULT_FROM_EMAIL  # Uses Django's default email
        super().__init__()

    def run(self):
        try:
            send_mail(
                self.subject, self.message, self.from_email, self.recipient_list, fail_silently=True
            )
        except Exception as e:
            logger.error(f"Email error: {e}")


def send_email_notification(subject, message, recipient_list):
    """
    Sends an email notification in a separate thread.
    """
    EmailThread(subject, message, recipient_list).start()
