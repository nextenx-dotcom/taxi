import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse

from .models import (
    User, DriverProfile, Car, Order, Trip, Payment,
    Notification, DeclinedOrder, SupportTicket, TicketMessage,
    TariffSettings
)
from .forms import (
    PassengerRegistrationForm, DriverRegistrationForm,
    CarForm, OrderForm, LoginForm, SupportTicketForm, TicketMessageForm
)


def index(request):
    return render(request, 'index.html')


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )
        if user:
            login(request, user)
            return _redirect_by_role(user)
        messages.error(request, 'Неверный логин или пароль')
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('index')


def _redirect_by_role(user):
    if user.role == 'driver':
        return redirect('driver_dashboard')
    if user.role == 'dispatcher':
        return redirect('dispatcher_dashboard')
    if user.role == 'admin' or user.is_superuser:
        return redirect('/admin/')
    return redirect('passenger_dashboard')


def register_passenger(request):
    form = PassengerRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Добро пожаловать!')
        return redirect('passenger_dashboard')
    return render(request, 'register_passenger.html', {'form': form})


def register_driver(request):
    if request.method == 'POST':
        user_form = DriverRegistrationForm(request.POST)
        car_form = CarForm(request.POST)
        if user_form.is_valid() and car_form.is_valid():
            user = user_form.save()
            car = car_form.save(commit=False)
            car.driver = user.driverprofile
            car.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла! Ожидайте верификации от диспетчера.')
            return redirect('driver_dashboard')
    else:
        user_form = DriverRegistrationForm()
        car_form = CarForm()
    return render(request, 'register_driver.html', {
        'user_form': user_form, 'car_form': car_form,
    })


#  ПАССАЖИР 

@login_required
def passenger_dashboard(request):
    if request.user.role == 'driver':
        return redirect('driver_dashboard')
    if request.user.role == 'dispatcher':
        return redirect('dispatcher_dashboard')
    orders = Order.objects.filter(passenger=request.user).order_by('-created_at')
    active_orders = orders.filter(status__in=['created', 'assigned', 'on_the_way'])
    history_orders = orders.filter(status__in=['completed', 'cancelled'])
    open_tickets = SupportTicket.objects.filter(
        user=request.user
    ).exclude(status='closed').count()
    return render(request, 'passenger_dashboard.html', {
        'active_orders': active_orders,
        'history_orders': history_orders,
        'total': orders.count(),
        'completed': orders.filter(status='completed').count(),
        'active_count': active_orders.count(),
        'open_tickets': open_tickets,
    })


@login_required
def create_order(request):
    if request.user.role != 'passenger':
        return redirect('driver_dashboard')
    form = OrderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        order = form.save(commit=False)
        order.passenger = request.user
        order.pickup_lat = request.POST.get('pickup_lat') or None
        order.pickup_lon = request.POST.get('pickup_lon') or None
        order.dest_lat = request.POST.get('dest_lat') or None
        order.dest_lon = request.POST.get('dest_lon') or None

        # Расчёт цены по тарифу из БД
        try:
            tariff = TariffSettings.get_current()
            dist = float(request.POST.get('distance_km', 0))
            calculated = float(tariff.boarding_fee) + dist * float(tariff.price_per_km)
            order.price = round(max(float(tariff.minimum_price), calculated), 2)
        except (ValueError, TypeError):
            tariff = TariffSettings.get_current()
            order.price = float(tariff.minimum_price)

        order.save()

        for dp in DriverProfile.objects.filter(verification_status='verified').select_related('user'):
            Notification.objects.create(
                user=dp.user, order=order,
                message=(
                    f"Новый заказ #{order.id}: "
                    f"{order.pickup_address} → {order.destination_address}. "
                    f"Цена: {order.price} ₽"
                )
            )
        messages.success(request, f'Заказ #{order.id} создан! Ищем водителя...')
        return redirect('order_detail', order_id=order.id)
    return render(request, 'create_order.html', {'form': form})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, passenger=request.user)
    driver_car = None
    if order.driver:
        driver_car = Car.objects.filter(driver=order.driver).first()
    return render(request, 'order_detail.html', {'order': order, 'driver_car': driver_car})


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, passenger=request.user)
    if order.status in ('created', 'assigned'):
        order.status = 'cancelled'
        order.save()
        messages.info(request, f'Заказ #{order.id} отменён.')
    return redirect('passenger_dashboard')


# ВОДИТЕЛЬ

@login_required
def driver_dashboard(request):
    if request.user.role != 'driver':
        return redirect('passenger_dashboard')
    try:
        profile = request.user.driverprofile
    except DriverProfile.DoesNotExist:
        return redirect('index')

    active_order = Order.objects.filter(
        driver=profile, status__in=['assigned', 'on_the_way']
    ).first()

    available_orders = []
    if profile.verification_status == 'verified' and not active_order:
        declined_ids = DeclinedOrder.objects.filter(
            driver=profile
        ).values_list('order_id', flat=True)
        available_orders = list(
            Order.objects.filter(
                status='created', driver__isnull=True
            ).exclude(id__in=declined_ids).order_by('-created_at')
        )

    open_tickets = SupportTicket.objects.filter(
        user=request.user
    ).exclude(status='closed').count()

    return render(request, 'driver_dashboard.html', {
        'profile': profile,
        'active_order': active_order,
        'available_orders': available_orders,
        'completed_orders': Order.objects.filter(
            driver=profile, status='completed'
        ).order_by('-created_at')[:10],
        'cars': Car.objects.filter(driver=profile),
        'open_tickets': open_tickets,
    })


@login_required
def accept_order(request, order_id):
    if request.user.role != 'driver':
        return redirect('index')
    profile = request.user.driverprofile
    if profile.verification_status != 'verified':
        messages.error(request, 'Вы не верифицированы.')
        return redirect('driver_dashboard')
    order = get_object_or_404(Order, id=order_id)
    if order.status != 'created' or order.driver is not None:
        messages.error(request, 'Заказ уже недоступен.')
        return redirect('driver_dashboard')
    if Order.objects.filter(driver=profile, status__in=['assigned', 'on_the_way']).exists():
        messages.error(request, 'Сначала завершите текущий заказ.')
        return redirect('driver_dashboard')
    order.driver = profile
    order.status = 'assigned'
    order.save()
    Notification.objects.create(
        user=order.passenger, order=order,
        message=f"Водитель {request.user.get_full_name() or request.user.username} принял ваш заказ #{order.id}!"
    )
    messages.success(request, f'Вы приняли заказ #{order.id}!')
    return redirect('driver_dashboard')


@login_required
def decline_order(request, order_id):
    if request.user.role != 'driver':
        return redirect('index')
    try:
        profile = request.user.driverprofile
        order = get_object_or_404(Order, id=order_id)
        DeclinedOrder.objects.get_or_create(driver=profile, order=order)
    except Exception:
        pass
    return redirect('driver_dashboard')


@login_required
@require_POST
def update_order_status(request, order_id):
    if request.user.role != 'driver':
        return redirect('index')
    profile = request.user.driverprofile
    order = get_object_or_404(Order, id=order_id, driver=profile)
    new_status = request.POST.get('status')
    transitions = {'assigned': 'on_the_way', 'on_the_way': 'completed'}
    if order.status in transitions and transitions[order.status] == new_status:
        order.status = new_status
        order.save()
        if new_status == 'on_the_way':
            Trip.objects.get_or_create(order=order, defaults={'started_at': timezone.now()})
            Notification.objects.create(
                user=order.passenger, order=order,
                message=f"Водитель выехал! Ожидайте: {order.pickup_address}"
            )
        elif new_status == 'completed':
            trip, _ = Trip.objects.get_or_create(order=order)
            trip.finished_at = timezone.now()
            trip.final_price = order.price
            trip.save()
            Notification.objects.create(
                user=order.passenger, order=order,
                message=f"Поездка завершена! Итого: {order.price} ₽"
            )
        messages.success(request, 'Статус обновлён.')
    return redirect('driver_dashboard')


@login_required
def toggle_driver_status(request):
    if request.user.role != 'driver':
        return redirect('index')
    profile = request.user.driverprofile
    if profile.verification_status != 'verified':
        messages.error(request, 'Только верифицированные водители могут выходить на линию.')
        return redirect('driver_dashboard')
    profile.is_active = not profile.is_active
    profile.save()
    messages.success(request, f"Статус: {'на линии' if profile.is_active else 'не на линии'}.")
    return redirect('driver_dashboard')


@login_required
def add_car(request):
    if request.user.role != 'driver':
        return redirect('index')
    profile = request.user.driverprofile
    form = CarForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        car = form.save(commit=False)
        car.driver = profile
        car.save()
        messages.success(request, 'Автомобиль добавлен!')
        return redirect('driver_dashboard')
    return render(request, 'add_car.html', {'form': form})


# ДИСПЕТЧЕР

def dispatcher_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ('dispatcher', 'admin') and not request.user.is_superuser:
            messages.error(request, 'Доступ запрещён.')
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return wrapper


@dispatcher_required
def dispatcher_dashboard(request):
    pending_drivers = DriverProfile.objects.filter(
        verification_status='pending'
    ).select_related('user').prefetch_related('cars')
    verified_drivers = DriverProfile.objects.filter(
        verification_status='verified'
    ).select_related('user')
    rejected_drivers = DriverProfile.objects.filter(
        verification_status='rejected'
    ).select_related('user')
    open_tickets = SupportTicket.objects.filter(
        status__in=['open', 'in_progress']
    ).select_related('user', 'assigned_to').order_by('-updated_at')
    all_orders = Order.objects.select_related(
        'passenger', 'driver__user'
    ).order_by('-created_at')[:20]
    stats = {
        'pending': pending_drivers.count(),
        'verified': verified_drivers.count(),
        'open_tickets': open_tickets.count(),
        'active_orders': Order.objects.filter(
            status__in=['created', 'assigned', 'on_the_way']
        ).count(),
        'total_orders': Order.objects.count(),
        'total_users': User.objects.filter(role='passenger').count(),
    }
    return render(request, 'dispatcher_dashboard.html', {
        'pending_drivers': pending_drivers,
        'verified_drivers': verified_drivers,
        'rejected_drivers': rejected_drivers,
        'open_tickets': open_tickets,
        'all_orders': all_orders,
        'stats': stats,
    })


@dispatcher_required
def verify_driver(request, driver_id):
    profile = get_object_or_404(DriverProfile, id=driver_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        if action == 'verify':
            profile.verification_status = 'verified'
            profile.is_active = True
            profile.verification_comment = comment
            profile.verified_by = request.user
            profile.verified_at = timezone.now()
            profile.save()
            Notification.objects.create(
                user=profile.user,
                message=' Ваш аккаунт верифицирован! Теперь вы можете принимать заказы.'
            )
            messages.success(request, f'Водитель {profile.user.username} верифицирован.')
        elif action == 'reject':
            profile.verification_status = 'rejected'
            profile.is_active = False
            profile.verification_comment = comment
            profile.verified_by = request.user
            profile.verified_at = timezone.now()
            profile.save()
            Notification.objects.create(
                user=profile.user,
                message=f' Аккаунт не прошёл верификацию. Причина: {comment or "не указана"}.'
            )
            messages.warning(request, f'Водитель {profile.user.username} отклонён.')
        elif action == 'reset':
            profile.verification_status = 'pending'
            profile.is_active = False
            profile.verification_comment = ''
            profile.save()
            messages.info(request, 'Статус водителя сброшен.')
    return redirect('dispatcher_dashboard')


@dispatcher_required
def dispatcher_driver_detail(request, driver_id):
    profile = get_object_or_404(
        DriverProfile.objects.select_related('user', 'verified_by').prefetch_related('cars'),
        id=driver_id
    )
    orders = Order.objects.filter(driver=profile).order_by('-created_at')[:20]
    return render(request, 'dispatcher_driver_detail.html', {
        'profile': profile, 'orders': orders,
    })


# ТИКЕТЫ

@login_required
def ticket_list(request):
    if request.user.role in ('dispatcher', 'admin') or request.user.is_superuser:
        tickets = SupportTicket.objects.select_related(
            'user', 'assigned_to'
        ).order_by('-updated_at')
        if request.GET.get('status'):
            tickets = tickets.filter(status=request.GET['status'])
    else:
        tickets = SupportTicket.objects.filter(
            user=request.user
        ).order_by('-updated_at')
    return render(request, 'ticket_list.html', {'tickets': tickets})


@login_required
def ticket_create(request):
    if request.user.role in ('dispatcher', 'admin'):
        return redirect('ticket_list')
    form = SupportTicketForm(request.POST or None)
    orders = []
    if request.user.role == 'passenger':
        orders = Order.objects.filter(passenger=request.user).order_by('-created_at')[:10]
    elif request.user.role == 'driver':
        try:
            orders = Order.objects.filter(
                driver=request.user.driverprofile
            ).order_by('-created_at')[:10]
        except Exception:
            pass
    if request.method == 'POST' and form.is_valid():
        ticket = form.save(commit=False)
        ticket.user = request.user
        order_id = request.POST.get('order_id')
        if order_id:
            try:
                ticket.order = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                pass
        ticket.save()
        first_msg = request.POST.get('first_message', '').strip()
        if first_msg:
            TicketMessage.objects.create(ticket=ticket, sender=request.user, text=first_msg)
        for d in User.objects.filter(role='dispatcher'):
            Notification.objects.create(
                user=d,
                message=f"Новое обращение #{ticket.id} от "
                        f"{request.user.get_full_name() or request.user.username}: {ticket.subject}"
            )
        messages.success(request, f'Обращение #{ticket.id} создано!')
        return redirect('ticket_detail', ticket_id=ticket.id)
    return render(request, 'ticket_create.html', {'form': form, 'orders': orders})


@login_required
def ticket_detail(request, ticket_id):
    if request.user.role in ('dispatcher', 'admin') or request.user.is_superuser:
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
    else:
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    if request.user.role in ('dispatcher', 'admin'):
        ticket.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        if ticket.status == 'open':
            ticket.status = 'in_progress'
            ticket.assigned_to = request.user
            ticket.save()
    else:
        ticket.messages.filter(is_read=False, sender__role='dispatcher').update(is_read=True)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            TicketMessage.objects.create(ticket=ticket, sender=request.user, text=text)
            ticket.save()
            if request.user.role in ('dispatcher', 'admin'):
                Notification.objects.create(
                    user=ticket.user,
                    message=f"Диспетчер ответил в обращении #{ticket.id}"
                )
            else:
                for d in User.objects.filter(role='dispatcher'):
                    Notification.objects.create(
                        user=d,
                        message=f"Новое сообщение в обращении #{ticket.id} от "
                                f"{request.user.get_full_name() or request.user.username}"
                    )
        return redirect('ticket_detail', ticket_id=ticket.id)
    ticket_messages = ticket.messages.select_related('sender').order_by('created_at')
    return render(request, 'ticket_detail.html', {
        'ticket': ticket, 'ticket_messages': ticket_messages,
    })


@dispatcher_required
def ticket_close(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    ticket.status = 'closed'
    ticket.save()
    Notification.objects.create(
        user=ticket.user, message=f"Ваше обращение #{ticket.id} закрыто."
    )
    messages.success(request, f'Обращение #{ticket.id} закрыто.')
    return redirect('ticket_detail', ticket_id=ticket.id)


@dispatcher_required
def ticket_reopen(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    ticket.status = 'in_progress'
    ticket.save()
    messages.info(request, f'Обращение #{ticket.id} переоткрыто.')
    return redirect('ticket_detail', ticket_id=ticket.id)


# API

@login_required
@require_POST
def update_driver_location(request):
    if request.user.role != 'driver':
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    try:
        data = json.loads(request.body)
        profile = request.user.driverprofile
        profile.latitude = data.get('lat')
        profile.longitude = data.get('lon')
        profile.save(update_fields=['latitude', 'longitude'])
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_driver_location(request, order_id):
    order = get_object_or_404(Order, id=order_id, passenger=request.user)
    if order.driver and order.status in ('assigned', 'on_the_way'):
        dp = order.driver
        return JsonResponse({
            'lat': dp.latitude, 'lon': dp.longitude,
            'status': order.status,
            'driver_name': dp.user.get_full_name() or dp.user.username,
            'driver_phone': dp.user.phone,
            'rating': dp.rating,
        })
    return JsonResponse({'status': order.status})


@login_required
def get_notifications(request):
    notifs = Notification.objects.filter(
        user=request.user, is_read=False
    ).select_related('order').order_by('-created_at')[:20]
    return JsonResponse({'notifications': [{
        'id': n.id, 'message': n.message,
        'order_id': n.order_id,
        'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
    } for n in notifs]})


@login_required
@require_POST
def mark_notification_read(request, notif_id):
    Notification.objects.filter(id=notif_id, user=request.user).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
def get_new_messages(request, ticket_id):
    if request.user.role in ('dispatcher', 'admin'):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
    else:
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    after_id = request.GET.get('after', 0)
    msgs = ticket.messages.filter(id__gt=after_id).select_related('sender')
    return JsonResponse({'messages': [{
        'id': m.id,
        'sender': m.sender.get_full_name() or m.sender.username,
        'sender_role': m.sender.role,
        'text': m.text,
        'created_at': m.created_at.strftime('%H:%M'),
        'is_mine': m.sender_id == request.user.id,
    } for m in msgs]})


@login_required
def get_available_orders(request):
    if request.user.role != 'driver':
        return JsonResponse({'count': 0})
    try:
        profile = request.user.driverprofile
        if profile.verification_status != 'verified':
            return JsonResponse({'count': 0})
        declined_ids = DeclinedOrder.objects.filter(
            driver=profile
        ).values_list('order_id', flat=True)
        count = Order.objects.filter(
            status='created', driver__isnull=True
        ).exclude(id__in=declined_ids).count()
        return JsonResponse({'count': count})
    except Exception:
        return JsonResponse({'count': 0})


@login_required
def get_orders_html(request):
    """Возвращает HTML-фрагмент со списком заказов — без перезагрузки страницы"""
    if request.user.role != 'driver':
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    try:
        profile = request.user.driverprofile
    except DriverProfile.DoesNotExist:
        return JsonResponse({'html': '', 'count': 0})

    if profile.verification_status != 'verified':
        return JsonResponse({'html': '', 'count': 0})

    active_order = Order.objects.filter(
        driver=profile, status__in=['assigned', 'on_the_way']
    ).first()
    if active_order:
        return JsonResponse({'html': '', 'count': 0, 'has_active': True})

    declined_ids = DeclinedOrder.objects.filter(
        driver=profile
    ).values_list('order_id', flat=True)
    available_orders = list(
        Order.objects.filter(
            status='created', driver__isnull=True
        ).exclude(id__in=declined_ids).order_by('-created_at')
    )

    if not available_orders:
        html = '''<div style="text-align:center;padding:2rem;color:var(--muted)">
            <div style="font-size:2.5rem;margin-bottom:0.5rem;opacity:0.4"></div>
            <div>Новых заказов нет</div></div>'''
    else:
        parts = []
        for order in available_orders:
            comment_block = (
                f'<div style="font-size:0.85rem;color:var(--muted);margin-bottom:0.8rem"> {order.comment}</div>'
                if order.comment else ''
            )
            price_block = (
                f'<span style="font-family:\'Bebas Neue\',sans-serif;font-size:1.5rem;color:var(--yellow)">{order.price} ₽</span>'
                if order.price else ''
            )
            accept_url = reverse('accept_order', args=[order.id])
            decline_url = reverse('decline_order', args=[order.id])
            time_str = order.created_at.strftime('%H:%M')
            parts.append(f'''<div class="new-order">
                <div class="new-badge"> Новый заказ #{order.id}</div>
                <div style="font-weight:600"> {order.pickup_address}</div>
                <div style="color:var(--muted);margin:0.3rem 0">↓</div>
                <div style="color:var(--muted)"> {order.destination_address}</div>
                <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin:0.8rem 0">
                    {price_block}
                    <span style="color:var(--muted);font-size:0.8rem">{time_str}</span>
                </div>
                {comment_block}
                <div style="display:flex;gap:0.8rem">
                    <a href="{accept_url}" class="btn btn-primary"> Принять</a>
                    <a href="{decline_url}" class="btn btn-ghost"> Пропустить</a>
                </div></div>''')
        html = ''.join(parts)

    return JsonResponse({'html': html, 'count': len(available_orders)})


def get_tariff(request):
    """API: текущий тариф для расчёта цены на клиенте"""
    tariff = TariffSettings.get_current()
    return JsonResponse({
        'price_per_km': float(tariff.price_per_km),
        'minimum_price': float(tariff.minimum_price),
        'boarding_fee': float(tariff.boarding_fee),
    })
