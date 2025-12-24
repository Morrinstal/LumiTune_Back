from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.forms import ValidationError
from django.urls import reverse 
from django.utils import timezone 
from django.utils import timezone as dj_timezone

class Track(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    artistid = models.CharField(max_length=100, null=True, blank=True)  
    genreid = models.CharField(max_length=100, null=True, blank=True)
    albumid = models.CharField(max_length=100, null=True, blank=True)

    artist = models.ForeignKey('ArtistLinks', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='tracks')

    playsnum = models.CharField(max_length=100, default='0')
    adult = models.BooleanField(default=False)
    time = models.FloatField(default=0.0)
    audio = models.FileField(upload_to='tracks/', null=True, blank=True)
    cover = models.ImageField(upload_to='covers/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not extra_fields.get('is_admin'):
            raise ValueError('Суперпользователь должен иметь is_admin=True')
        if not extra_fields.get('is_staff'):
            raise ValueError('Суперпользователь должен иметь is_staff=True')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Суперпользователь должен иметь is_superuser=True')
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_admin = models.BooleanField(default=False, verbose_name='Administrator')
    is_client = models.BooleanField(default=False, verbose_name='Client')
    is_staff = models.BooleanField(default=False) 
    is_active = models.BooleanField(default=True)
    full_name = models.CharField(max_length=255, blank=True)
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
class Playlist(models.Model):
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    cover = models.ImageField(upload_to='playlist_covers/', null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='playlists'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, related_name='items', on_delete=models.CASCADE)
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']
        unique_together = [('playlist', 'track')]


def cover_upload_to(instance, filename):
    return f"covers/{instance.__class__.__name__.lower()}/{filename}"
def audio_upload_to(instance, filename):
    return f"audio/{instance.__class__.__name__.lower()}/{filename}"

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    update_at  = models.DateTimeField(auto_now=True,null=True)

    class Meta:
        abstract = True   # ← обязательно


class AudioBook(TimeStamped):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)  

    author_fk = models.ForeignKey('ArtistLinks', null=True, blank=True, on_delete=models.SET_NULL, related_name='audiobooks')
    genreid = models.CharField(max_length=64, blank=True)
    playsnum = models.IntegerField(default=0)
    adult = models.BooleanField(default=False)
    duration_seconds = models.IntegerField(null=True, blank=True)
    info = models.TextField(blank=True)
    chapter = models.IntegerField(null=True, blank=True)
    audio_file = models.FileField(upload_to=audio_upload_to, null=True, blank=True)
    cover_image = models.ImageField(upload_to=cover_upload_to, null=True, blank=True)
    def cover_url(self): return self.cover_image.url if self.cover_image else ""
    def audio_url(self): return self.audio_file.url if self.audio_file else ""

class PodcastEpisode(TimeStamped):
    title = models.CharField(max_length=255)
    episode = models.IntegerField(null=True, blank=True)
    host = models.CharField(max_length=255, blank=True, null=True)  

    host_fk = models.ForeignKey('ArtistLinks', null=True, blank=True, on_delete=models.SET_NULL, related_name='podcasts')

    genreid = models.CharField(max_length=64, blank=True)
    playsnum = models.IntegerField(default=0)
    adult = models.BooleanField(default=False)
    duration_seconds = models.IntegerField(null=True, blank=True)
    info = models.TextField(blank=True)
    audio_file = models.FileField(upload_to=audio_upload_to, null=True, blank=True)
    cover_image = models.ImageField(upload_to=cover_upload_to, null=True, blank=True)
    def cover_url(self): return self.cover_image.url if self.cover_image else ""
    def audio_url(self): return self.audio_file.url if self.audio_file else ""
class ArtistLinks(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='artists/', null=True, blank=True)
    listeners = models.CharField(max_length=32, blank=True, default='0')

    # ВАЖНО: один плейлист на артиста
    playlist = models.OneToOneField(
        'Playlist',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='artist'
    )

    def __str__(self): return self.name
def validate_min_age(value):
    if not value:
        return
    today = timezone.now().date()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 12:
        raise ValidationError("Користувачу має бути не менше 12 років.")

class Profile(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Звичайний користувач"
        AUTHOR = "author", "Автор пісень"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    display_name = models.CharField(max_length=255, blank=True)
    date_of_birth = models.DateField(null=True, blank=True, validators=[validate_min_age])
    country_code = models.CharField(max_length=2, blank=True, db_index=True)  # ISO2: UA/PL/US...
    city = models.CharField(max_length=120, blank=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    update_at  = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"Profile<{self.user.email}>"
class PasswordResetCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_codes")
    code = models.CharField(max_length=6)               # можно хранить в открытом виде для dev
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)   # антибрутфорс, опционально

    def is_valid(self) -> bool:
        return (not self.used) and (dj_timezone.now() < self.expires_at) and (self.attempts < 5)