from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.core.mail import send_mail
from .models import Parcel, Driver
from .serializers import*
from .utils import send_sms,get_coordinates, send_email_notification
from .tasks import send_email_async
from .permissions import IsCustomer, IsAdmin, IsDriver
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.conf import settings
from .tasks import send_email_async, send_sms_async
from django.db import transaction
import stripe

stripe.api_key = settings.STRIPE_API_KEY
CENTS_PER_DOLLAR = 100

import logging
logger = logging.getLogger(__name__)



class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(["POST"])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Stripe webhook signature verification failed: {e}")
        return Response({"error": "Invalid signature"}, status=400)

    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        tracking_code = payment_intent["metadata"]["tracking_code"]
        Parcel.objects.filter(tracking_code=tracking_code).update(payment_status="paid")
        logger.info(f"Payment succeeded for parcel {tracking_code}")

    return Response({"message": "Webhook received"}, status=200)



# List & Create Parcels
class ParcelListCreateView(generics.ListCreateAPIView):
    serializer_class = ParcelSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def get_queryset(self):
        return Parcel.objects.filter(sender=self.request.user).select_related('sender', 'assigned_driver')
    
    def perform_create(self, serializer):
        parcel = serializer.save(sender=self.request.user)
        # Get recipient address coordinates
        lat, lng = get_coordinates(parcel.recipient_address)
        if lat and lng:
            parcel.current_latitude = lat
            parcel.current_longitude = lng
            parcel.save()
    
        # subject = "Parcel Created Successfully"
        # message = f"Your parcel with tracking code {parcel.tracking_code} has been created."
        # send_email_async.delay(subject, message, [self.request.user.email])

        # # Send SMS notification
        # if self.request.user.profile.phone_number:
        #     sms_message = f"Your parcel {parcel.tracking_code} has been registered. Track it online."
        #     send_sms(self.request.user.profile.phone_number, sms_message)



# Retrieve, Update, Delete Parcels
class ParcelDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ParcelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Parcel.objects.filter(sender=self.request.user)

    def perform_update(self, serializer):
        parcel = serializer.save()

        # # Send email notification
        # subject = "Parcel Status Update",
        # message = f"Your parcel {parcel.tracking_code} is now {parcel.status}."
        # send_email_notification(subject, message, [self.request.user.email])

        # # Send SMS notification
        # if self.request.user.profile.phone_number:
        #     sms_message =  f"Your parcel {parcel.tracking_code} is now {parcel.status}."
        #     send_sms(self.request.user.profile.phone_number, sms_message)



# Assign Parcel to Driver
# @login_required
@api_view(['POST'])
@permission_classes([permissions.IsAdminUser, IsAdmin])
def assign_driver(request, parcel_id, driver_id):
    with transaction.atomic():
        parcel = get_object_or_404(Parcel, id=parcel_id)
        driver = get_object_or_404(Driver, id=driver_id)
        if parcel.assigned_driver:
            return Response({"error": "Parcel already assigned."}, status=400)
        # Check driver availability (e.g., max 5 active parcels)
        active_parcels = Parcel.objects.filter(assigned_driver=driver, status__in=["assigned", "in_transit"]).count()
        if active_parcels >= 5:
            return Response({"error": "Driver has too many active parcels."}, status=400)
        parcel.assigned_driver = driver
        parcel.status = "assigned"
        parcel.save()

    if driver.phone:
        send_sms_async.delay(driver.phone, f"You've been assigned a new parcel: {parcel.tracking_code}")
    if parcel.sender.profile.phone_number:
        send_sms_async.delay(parcel.sender.profile.phone_number, f"Your parcel {parcel.tracking_code} is assigned to {driver.name}")
    send_email_async.delay(
        "Driver Assigned to Your Parcel",
        f"Your parcel {parcel.tracking_code} is now assigned to {driver.name}.",
        [parcel.sender.email]
    )
    return Response({"message": "Driver assigned successfully"}, status=200)


# Create and View Drivers
class DriverListCreateView(generics.ListCreateAPIView):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [permissions.IsAdminUser]


class DriverDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [permissions.IsAdminUser]


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def process_payment(request, parcel_id):
    parcel = get_object_or_404(Parcel, id=parcel_id)
    if parcel.payment_status == "paid":
        return Response({"error": "Parcel is already paid for."}, status=400)
    
    serializer = PaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(parcel.price * CENTS_PER_DOLLAR),
            currency="usd",
            description=f"Payment for parcel {parcel.tracking_code}",
            payment_method=serializer.validated_data["payment_method_id"],
            confirm=True,
            metadata={"tracking_code": parcel.tracking_code}  # Ensure tracking_code is passed
        )

        parcel.payment_status = "paid"
        parcel.save()

        # send_email_notification(
        #     "Payment Successful for Your Parcel",
        #     f"Your payment of ${parcel.price} for parcel {parcel.tracking_code} was successful.",
        #     [parcel.sender.email]  # Changed from parcel.user.email
        # )
        # if parcel.sender.profile.phone_number:  # Changed from parcel.user.profile.phone_number
        #     send_sms(
        #         parcel.sender.profile.phone_number,
        #         f"Payment of ${parcel.price} for {parcel.tracking_code} received."
        #     )

        return Response({"message": "Payment successful", "client_secret": intent.client_secret}, status=200)
    except stripe.error.CardError as e:
        logger.error(f"Card error for parcel {parcel.tracking_code}: {e.user_message}")
        return Response({"error": f"Card error: {e.user_message}"}, status=400)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error for parcel {parcel.tracking_code}: {str(e)}")
        return Response({"error": f"Payment error: {str(e)}"}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in process_payment for parcel {parcel.tracking_code}: {e}")
        return Response({"error": "Server error. Please try again."}, status=500)


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated, IsDriver])
def update_location(request, parcel_id):
    parcel = get_object_or_404(Parcel, id=parcel_id, assigned_driver__user=request.user)
    serializer = ParcelUpdateLocationSerializer(parcel, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        cache.delete(parcel.tracking_code)  # Invalidate cache
        return Response({"message": "Location updated", "data": serializer.data}, status=200)
    return Response(serializer.errors, status=400)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def track_parcel(request, tracking_code):
    cached_data = cache.get(tracking_code)
    if cached_data:
        return Response(cached_data, status=200)

    parcel = get_object_or_404(Parcel, tracking_code=tracking_code)
    data = {
        "tracking_code": parcel.tracking_code,
        "status": parcel.status,
        "assigned_driver": parcel.assigned_driver.name if parcel.assigned_driver else "Not Assigned",
    }

    # Cache for 1 hour, or less if status is dynamic
    cache_timeout = 3600 if parcel.status in ["delivered", "confirmed", "cancelled"] else 300
    cache.set(tracking_code, data, timeout=cache_timeout)
    return Response(data, status=200)


@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated, IsCustomer])
def confirm_delivery(request, tracking_code):
    try:
        parcel = Parcel.objects.get(tracking_code=tracking_code, sender=request.user)

        if parcel.status != "delivered":
            return Response({"error": "Parcel has not been marked as delivered yet"}, status=400)

        parcel.status = "confirmed"
        parcel.save()

        
        subject = "Parcel Delivery Confirmed"
        message = f"The customer has confirmed the delivery of parcel {tracking_code}."
        send_email_notification(subject, message, [parcel.assigned_driver.email])

        return Response({"message": "Delivery confirmed successfully"}, status=200)

    except Parcel.DoesNotExist:
        return Response({"error": "Parcel not found or you are not the owner"}, status=404)



@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_dashboard(request):
    user = request.user
    if user.role == "admin":
        parcels = Parcel.objects.all().select_related('sender', 'assigned_driver')
    elif user.role == "driver":
        parcels = Parcel.objects.filter(assigned_driver__user=user).select_related('sender')
    else:
        parcels = Parcel.objects.filter(sender=user).select_related('assigned_driver')

    paginator = StandardPagination()
    result_page = paginator.paginate_queryset(parcels, request)

    data = [
        {
            "tracking_code": parcel.tracking_code,
            "recipient_name": parcel.recipient_name,
            "recipient_address": parcel.recipient_address if user.role in ["admin", "driver"] else None,
            "recipient_phone": parcel.recipient_phone if user.role in ["admin", "driver"] else None,
            "status": parcel.status,
            "current_latitude": parcel.current_latitude,
            "current_longitude": parcel.current_longitude,
            "assigned_driver": parcel.assigned_driver.name if parcel.assigned_driver else None,
        }
        for parcel in result_page
    ]
    return paginator.get_paginated_response(data)

@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated, IsDriver])
def update_location(request, parcel_id):
    """
    Update the current location of a parcel.
    Only the assigned driver can update the location.
    Args:
        request: HTTP request with latitude/longitude data
        parcel_id: UUID of the parcel
    Returns:
        200: Location updated successfully
        400: Invalid data
        404: Parcel not found or unauthorized
    """
    parcel = get_object_or_404(Parcel, id=parcel_id, assigned_driver__user=request.user)
    serializer = ParcelUpdateLocationSerializer(parcel, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        cache.delete(parcel.tracking_code)
        return Response({"message": "Location updated", "data": serializer.data}, status=200)
    return Response(serializer.errors, status=400)