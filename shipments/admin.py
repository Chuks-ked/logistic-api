from django.contrib import admin
from .models import Driver, Parcel


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "license_number", "created_at")
    search_fields = ("name", "email", "phone", "license_number")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ("tracking_code", "sender", "receiver", "origin", "destination", "status", "assigned_driver", "payment_status", "created_at")  
    search_fields = ("tracking_code", "sender", "receiver", "origin", "destination")
    list_filter = ("status", "is_paid", "is_delivered", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Parcel Information", {"fields": ("tracking_code", "sender", "receiver", "origin", "destination", "weight", "status")}),
        ("Driver & Payment", {"fields": ("assigned_driver", "is_paid", "is_delivered")}),
    )
