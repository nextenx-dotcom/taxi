from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/passenger/', views.register_passenger, name='register_passenger'),
    path('register/driver/', views.register_driver, name='register_driver'),

    # Пассажир
    path('dashboard/', views.passenger_dashboard, name='passenger_dashboard'),
    path('order/create/', views.create_order, name='create_order'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),

    # Водитель
    path('driver/', views.driver_dashboard, name='driver_dashboard'),
    path('driver/order/<int:order_id>/accept/', views.accept_order, name='accept_order'),
    path('driver/order/<int:order_id>/decline/', views.decline_order, name='decline_order'),
    path('driver/order/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('driver/location/', views.update_driver_location, name='update_driver_location'),
    path('driver/car/add/', views.add_car, name='add_car'),
    path('driver/toggle-status/', views.toggle_driver_status, name='toggle_driver_status'),

    # Диспетчер
    path('dispatcher/', views.dispatcher_dashboard, name='dispatcher_dashboard'),
    path('dispatcher/driver/<int:driver_id>/', views.dispatcher_driver_detail, name='dispatcher_driver_detail'),
    path('dispatcher/driver/<int:driver_id>/verify/', views.verify_driver, name='verify_driver'),

    # Тикеты
    path('support/', views.ticket_list, name='ticket_list'),
    path('support/new/', views.ticket_create, name='ticket_create'),
    path('support/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('support/<int:ticket_id>/close/', views.ticket_close, name='ticket_close'),
    path('support/<int:ticket_id>/reopen/', views.ticket_reopen, name='ticket_reopen'),

    # API
    path('api/driver-location/<int:order_id>/', views.get_driver_location, name='get_driver_location'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/tickets/<int:ticket_id>/messages/', views.get_new_messages, name='get_new_messages'),
    path('api/available-orders/', views.get_available_orders, name='get_available_orders'),
    path('api/orders-html/', views.get_orders_html, name='get_orders_html'),
    path('api/tariff/', views.get_tariff, name='get_tariff'),
]
