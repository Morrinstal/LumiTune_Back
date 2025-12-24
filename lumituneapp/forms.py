from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .models import CustomUser
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
class AdminLoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        user = authenticate(self.request, username=email, password=password)
        if user is None:
            raise forms.ValidationError("Неверный email или пароль.")
        if not user.is_admin:
            raise forms.ValidationError("Пользователь не является администратором.")
        self.user = user
        return self.cleaned_data

    def get_user(self):
        return self.user
    

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    repeat_password = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ('email',)  # Только email из модели

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        repeat_password = cleaned_data.get("repeat_password")
        if password and repeat_password and password != repeat_password:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_admin = True
        user.is_staff = True
        user.set_password(self.cleaned_data["password"])  # Хэшируем пароль
        if commit:
            user.save()
        return user