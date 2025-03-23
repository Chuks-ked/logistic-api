from django.test import TestCase
from rest_framework.test import APIClient
from .models import User, Profile, Parcel, Driver
from django.urls import reverse

class ParcelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="testpass", role="customer")
        Profile.objects.create(user=self.user, phone_number="+1234567890")
        self.driver = Driver.objects.create(user=User.objects.create_user(username="driver", password="testpass", role="driver"), name="Driver1", email="driver@test.com", phone="+0987654321", license_number="DRV123")
        self.parcel = Parcel.objects.create(
            tracking_code="TEST123", sender=self.user, recipient_name="John", recipient_address="123 St", 
            recipient_phone="+1234567890", origin="City A", destination="City B", price=10.00
        )
        self.client.force_authenticate(user=self.user)

    def test_create_parcel(self):
        response = self.client.post(reverse('parcel-list-create'), {
            "recipient_name": "Jane", "recipient_address": "456 St", "recipient_phone": "+0987654321",
            "origin": "City X", "destination": "City Y", "price": 15.00
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Parcel.objects.count(), 2)

    def test_track_parcel(self):
        response = self.client.get(reverse('track-parcel', kwargs={'tracking_code': 'TEST123'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tracking_code'], 'TEST123')

    def test_process_payment(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.post(
            f"/parcels/{self.parcel.id}/pay/",
            {"payment_method_id": "pm_test"},
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.payment_status, "paid")