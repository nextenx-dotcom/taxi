from django.contrib import admin, messages as django_messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, DriverProfile, Car, Order, Trip, Payment,
    Notification, DeclinedOrder, SupportTicket, TicketMessage,
    TariffSettings
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'role', 'phone', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('role', 'phone')}),
    )


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'license_number', 'verification_status', 'is_active', 'rating']
    list_filter = ['verification_status', 'is_active']
    readonly_fields = ['verified_at']


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ['driver', 'brand', 'model', 'plate_number', 'color']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'passenger', 'driver',
        'pickup_address', 'destination_address',
        'status', 'price', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['passenger__username', 'pickup_address', 'destination_address']
    readonly_fields = ['created_at']
    list_editable = ['price', 'status']

    fields = [
        'passenger', 'driver',
        'pickup_address', 'destination_address',
        'pickup_lat', 'pickup_lon', 'dest_lat', 'dest_lon',
        'status', 'price', 'comment', 'created_at',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('passenger', 'driver__user')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ['order', 'started_at', 'finished_at', 'distance_km', 'final_price']
    list_editable = ['final_price']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'method', 'status']
    list_editable = ['amount', 'status']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'is_read', 'created_at']
    list_filter = ['is_read']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'subject', 'category', 'status', 'assigned_to', 'updated_at']
    list_filter = ['status', 'category']
    search_fields = ['user__username', 'subject']


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'sender', 'created_at', 'is_read']
    list_filter = ['is_read']


@admin.register(TariffSettings)
class TariffSettingsAdmin(admin.ModelAdmin):
    list_display = ['price_per_km', 'minimum_price', 'boarding_fee', 'updated_at', 'updated_by']
    readonly_fields = ['updated_at', 'updated_by']

    fieldsets = (
        ('Настройки тарифа', {
            'description': (
                'Формула: Цена = Посадочный тариф + Расстояние × Цена за км. '
                'Итоговая цена не может быть меньше минимальной.'
            ),
            'fields': ('price_per_km', 'minimum_price', 'boarding_fee')
        }),
        ('Служебная информация', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return not TariffSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        django_messages.success(
            request,
            f'Тариф обновлён: {obj.price_per_km} ₽/км, '
            f'минимум {obj.minimum_price} ₽, '
            f'посадка {obj.boarding_fee} ₽'
        )
