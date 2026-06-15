from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, DriverProfile, Car, Order, SupportTicket


class PassengerRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, label='Имя', required=True)
    last_name = forms.CharField(max_length=50, label='Фамилия', required=True)
    phone = forms.CharField(max_length=20, label='Телефон', required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'passenger'
        user.phone = self.cleaned_data['phone']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class DriverRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, label='Имя', required=True)
    last_name = forms.CharField(max_length=50, label='Фамилия', required=True)
    phone = forms.CharField(max_length=20, label='Телефон', required=True)
    license_number = forms.CharField(max_length=50, label='Номер водительского удостоверения', required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'driver'
        user.phone = self.cleaned_data['phone']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            DriverProfile.objects.create(
                user=user,
                license_number=self.cleaned_data['license_number'],
                verification_status='pending',
                is_active=False,
            )
        return user


class DispatcherRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, label='Имя', required=True)
    last_name = forms.CharField(max_length=50, label='Фамилия', required=True)
    phone = forms.CharField(max_length=20, label='Телефон', required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'dispatcher'
        user.phone = self.cleaned_data['phone']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ['brand', 'model', 'plate_number', 'color']
        labels = {
            'brand': 'Марка', 'model': 'Модель',
            'plate_number': 'Гос. номер', 'color': 'Цвет',
        }


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['pickup_address', 'destination_address', 'comment']
        labels = {
            'pickup_address': 'Адрес подачи',
            'destination_address': 'Адрес назначения',
            'comment': 'Комментарий',
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Подъезд, этаж, пожелания...'}),
        }


class LoginForm(forms.Form):
    username = forms.CharField(label='Логин')
    password = forms.CharField(widget=forms.PasswordInput, label='Пароль')


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'category']
        labels = {
            'subject': 'Тема обращения',
            'category': 'Категория',
        }


class TicketMessageForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Введите сообщение...'}),
        label=''
    )
