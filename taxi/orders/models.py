from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('passenger', 'Пассажир'),
        ('driver', 'Водитель'),
        ('dispatcher', 'Диспетчер'),
        ('admin', 'Администратор'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='passenger')
    phone = models.CharField(max_length=20, default='0000000000')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class DriverProfile(models.Model):
    VERIFICATION_STATUS = (
        ('pending', 'На проверке'),
        ('verified', 'Верифицирован'),
        ('rejected', 'Отклонён'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    license_number = models.CharField(max_length=50)
    rating = models.FloatField(default=5.0)
    is_active = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS, default='pending'
    )
    verification_comment = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_drivers'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Водитель: {self.user.username} [{self.get_verification_status_display()}]"


class Car(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='cars')
    brand = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    plate_number = models.CharField(max_length=20)
    color = models.CharField(max_length=30, blank=True, null=True)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.plate_number})"


class Order(models.Model):
    STATUS_CHOICES = (
        ('created', 'Создан'),
        ('assigned', 'Принят водителем'),
        ('on_the_way', 'В пути'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    )
    passenger = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='orders'
    )
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders'
    )
    pickup_address = models.CharField(max_length=255)
    destination_address = models.CharField(max_length=255)
    pickup_lat = models.FloatField(null=True, blank=True)
    pickup_lon = models.FloatField(null=True, blank=True)
    dest_lat = models.FloatField(null=True, blank=True)
    dest_lon = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заказ #{self.id} — {self.passenger.username}"


class Trip(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    distance_km = models.FloatField(default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Поездка по заказу #{self.order.id}"


class Payment(models.Model):
    METHOD_CHOICES = (
        ('cash', 'Наличные'),
        ('card', 'Карта'),
    )
    STATUS_CHOICES = (
        ('pending', 'Ожидает'),
        ('paid', 'Оплачено'),
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Оплата заказа #{self.order.id}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Уведомление для {self.user.username}"

    class Meta:
        ordering = ['-created_at']


class DeclinedOrder(models.Model):
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name='declined_orders'
    )
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='declined_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('driver', 'order')


class SupportTicket(models.Model):
    STATUS_CHOICES = (
        ('open', 'Открыт'),
        ('in_progress', 'В работе'),
        ('closed', 'Закрыт'),
    )
    CATEGORY_CHOICES = (
        ('general', 'Общий вопрос'),
        ('order', 'Проблема с заказом'),
        ('payment', 'Оплата'),
        ('driver', 'Проблема с водителем'),
        ('technical', 'Техническая проблема'),
        ('other', 'Другое'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tickets'
    )
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Тикет #{self.id} — {self.subject} [{self.get_status_display()}]"

    def unread_count_for_dispatcher(self):
        return self.messages.filter(is_read=False).exclude(sender__role='dispatcher').count()

    def unread_count_for_user(self):
        return self.messages.filter(is_read=False, sender__role='dispatcher').count()


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Сообщение от {self.sender.username} в тикете #{self.ticket.id}"


class TariffSettings(models.Model):
    """Настройки тарифа — управляются через Django Admin"""
    price_per_km = models.DecimalField(
        max_digits=8, decimal_places=2, default=50.00,
        verbose_name='Цена за километр (₽)'
    )
    minimum_price = models.DecimalField(
        max_digits=8, decimal_places=2, default=150.00,
        verbose_name='Минимальная цена (₽)'
    )
    boarding_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00,
        verbose_name='Посадочный тариф (₽)'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Изменил', related_name='tariff_changes'
    )

    class Meta:
        verbose_name = 'Настройки тарифа'
        verbose_name_plural = 'Настройки тарифа'

    def __str__(self):
        return f"{self.price_per_km} ₽/км | мин. {self.minimum_price} ₽ | посадка {self.boarding_fee} ₽"

    @classmethod
    def get_current(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'price_per_km': 50.00,
                'minimum_price': 150.00,
                'boarding_fee': 0.00,
            }
        )
        return obj
