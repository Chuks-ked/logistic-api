from django.urls import path

from .views import (
    ParcelListCreateView, ParcelDetailView,
    DriverListCreateView, DriverDetailView, assign_driver, process_payment, update_location, track_parcel, confirm_delivery, user_dashboard
)

urlpatterns = [

    # Driver Routes
    path('drivers/', DriverListCreateView.as_view(), name='driver-list-create'),
    path('drivers/<int:pk>/', DriverDetailView.as_view(), name='driver-detail'),

    # Parcel Routes
    path('parcels/', ParcelListCreateView.as_view(), name='parcel-list-create'),
    path('parcels/<uuid:pk>/', ParcelDetailView.as_view(), name='parcel-detail'),
    path('parcels/<uuid:tracking_code>/track/', track_parcel, name='track-parcel'),
    path('parcels/<int:parcel_id>/pay/', process_payment, name='process-payment'),
    path('parcels/<int:parcel_id>/update-location/', update_location, name='update-location'),
    path('parcels/confirm/<str:tracking_code>/', confirm_delivery, name='confirm_delivery'),

    # Assignment and Dashboard
    path('parcels/<int:parcel_id>/assign-driver/<int:driver_id>/', assign_driver, name='assign-driver'),
    path('dashboard/', user_dashboard, name='dashboard'),

]
