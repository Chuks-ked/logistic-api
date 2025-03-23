from rest_framework import serializers
from .models import Driver, Parcel


# 🚛 Driver Serializer
class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "name", "email", "phone", "license_number", "created_at"]


class ParcelSerializer(serializers.ModelSerializer):
    current_latitude = serializers.FloatField(min_value=-90, max_value=90, allow_null=True)
    current_longitude = serializers.FloatField(min_value=-180, max_value=180, allow_null=True)
    
    class Meta:
        model = Parcel
        fields = [
            "id", "tracking_code", "sender", "recipient_name", "recipient_address",
            "recipient_phone", "origin", "destination", "status", "assigned_driver",
            "current_location", "current_latitude", "current_longitude", "price",
            "payment_status", "created_at"
        ]
        read_only_fields = ["tracking_code", "created_at", "sender"]


# 🔍 Parcel Tracking Serializer (Only shows relevant tracking fields)
class ParcelTrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcel
        fields = ["tracking_code", "origin", "destination", "status"]


# 📍 Update Location Serializer (Allows partial updates)
class ParcelUpdateLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcel
        fields = ["current_latitude", "current_longitude", "current_location"]


class PaymentSerializer(serializers.Serializer):
    payment_method_id = serializers.CharField(required=True)