import os
import re
import json
import uuid
import mimetypes
from datetime import datetime, time, timezone

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.core.paginator import Paginator, EmptyPage
from django.db import IntegrityError, transaction
from django.db.models import Q, DateTimeField, DateField, IntegerField, Sum, Count
from django.db.models.functions import TruncDate, Cast, Coalesce
from django.http import JsonResponse, FileResponse, StreamingHttpResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.timezone import get_current_timezone, make_aware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.utils.text import slugify
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
# если хочешь, чтобы параллельно работали и cookie-сессии, и JWT:
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import transaction
from django.db.models import Q
from .models import Profile  # если используешь select_related('profile')
from .forms import AdminLoginForm, RegistrationForm
from .models import (
    Playlist, PlaylistItem, Track,
    AudioBook, PodcastEpisode, ArtistLinks
)
from rest_framework import generics, permissions
from .serializers import RegisterSerializer, MeSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.mail import EmailMultiAlternatives, BadHeaderError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer
import logging
from django.contrib.auth.tokens import default_token_generator
from .models import PasswordResetCode  
from django.utils import timezone as dj_timezone  
import datetime as dt 
from .serializers import (
    RegisterSerializer, MeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    PasswordResetCodeVerifySerializer,  # <— вот это
    PasswordResetCodeConfirmSerializer,
)
from django.utils.text import slugify
import random
class RegisterAPIView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    authentication_classes = []  

class MeAPIView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user
User = get_user_model()
logger = logging.getLogger(__name__)
ALLOWED_FIELDS = {"albumid", "genreid", "artistid", "playlist"}


# =========================
# Auth / Admin pages
# =========================

def logout_view(request):
    logout(request)
    return redirect("login")


def admin_login_view(request):
    if request.method == 'POST':
        form = AdminLoginForm(request.POST, request=request)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('/api/dashboard/')
    else:
        form = AdminLoginForm()
    return render(request, 'custom_admin/login.html', {'form': form})


def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()                 # создаёт админа через твой менеджер
            Profile.objects.get_or_create(     # <- создаём пустой профиль, чтобы админа тоже "видно" в таблицах
                user=user,
                defaults={"display_name": user.full_name or user.email}
            )
            return redirect('/api/auth/')
    else:
        form = RegistrationForm()
    return render(request, 'custom_admin/register.html', {'form': form, 'MEDIA_URL': settings.MEDIA_URL})


class AdminPasswordResetView(PasswordResetView):
    template_name = 'custom_admin/password_reset_email.html'
    email_template_name = 'custom_admin/password_reset_email.html'
    success_url = '/admin/login/'
def _generate_code(k: int = 6) -> str:
    return "".join(random.choices("0123456789", k=k))

def generate_otp_code(k: int = 6) -> str:
    return _generate_code(k)

def _send_reset_code(email: str, code: str):
    subject = "Код для відновлення пароля • LumiTune"
    text = (
        "Вітаємо!\n\n"
        f"Ваш код для відновлення пароля: {code}\n"
        "Код дійсний 10 хвилин.\n\n"
        "Якщо ви не запитували відновлення — ігноруйте цей лист."
    )
    html = f"""
      <p>Вітаємо!</p>
      <p>Ваш код для відновлення пароля: <b style="font-size:18px">{code}</b></p>
      <p>Код дійсний 10 хвилин.</p>
      <p style="color:#888">Якщо ви не запитували відновлення — ігноруйте цей лист.</p>
    """
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [email])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)

class PasswordResetCodeRequestAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "Email is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # не палим существование
            return Response({"detail": "If the email exists, a code has been sent."},
                            status=status.HTTP_200_OK)

        # инвалидируем активные (исправлена опечатка ser=user -> user=user)
        PasswordResetCode.objects.filter(
            user=user, used=False, expires_at__gt=dj_timezone.now()
        ).update(used=True)

        code = "".join(__import__("random").choices("0123456789", k=6))

        PasswordResetCode.objects.create(
            user=user,
            code=code,
            expires_at=dj_timezone.now() + dt.timedelta(minutes=10),
            used=False,
            attempts=0,
        )

        try:
            subject = "Код для відновлення пароля • LumiTune"
            text = (
                f"Ваш одноразовий код для відновлення пароля: {code}\n\n"
                f"Код дійсний 10 хвилин. Якщо ви не запитували відновлення, просто ігноруйте цей лист."
            )
            html = f"""
            <p>Ваш одноразовий код для відновлення пароля:</p>
            <p style="font-size:20px;font-weight:700;letter-spacing:2px">{code}</p>
            <p style="color:#888">Код дійсний 10 хвилин. Якщо ви не запитували відновлення — просто ігноруйте цей лист.</p>
            """
            msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=False)
        except BadHeaderError:
            logger.exception("BadHeaderError while sending OTP")
        except Exception:
            logger.exception("SMTP error while sending OTP")

        return Response({"detail": "If the email exists, a code has been sent."},
                        status=status.HTTP_200_OK)


class PasswordResetCodeVerifyAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = PasswordResetCodeVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email = ser.validated_data["email"].strip().lower()
        code  = ser.validated_data["code"].strip()

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "Невірний код або e-mail."},
                            status=status.HTTP_400_BAD_REQUEST)

        prc = (
            PasswordResetCode.objects
            .filter(user=user, code=code)
            .order_by("-created_at")
            .first()
        )
        if not prc:
            return Response({"detail": "Невірний код або e-mail."},
                            status=status.HTTP_400_BAD_REQUEST)

        prc.attempts += 1
        prc.save(update_fields=["attempts"])

        if not prc.is_valid():
            return Response({"detail": "Код недійсний або прострочений."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok": True}, status=status.HTTP_200_OK)


class PasswordResetCodeConfirmAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = PasswordResetCodeConfirmSerializer(data=request.data)
        if not ser.is_valid():
            # Вернём подробные ошибки по полям, а не общий detail
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        email = ser.validated_data["email"].strip().lower()
        code = ser.validated_data["code"].strip()
        new_password = ser.validated_data["new_password"]

        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # не раскрываем базу
            return Response({"detail": "Invalid code or expired."}, status=status.HTTP_400_BAD_REQUEST)

        prc = (
            PasswordResetCode.objects
            .filter(user=user, code=code, used=False, expires_at__gt=dj_timezone.now())
            .order_by("-created_at")
            .first()
        )
        if not prc:
            return Response({"detail": "Токен недійсний або прострочений."},
                            status=status.HTTP_400_BAD_REQUEST)

        # на всякий случай проверим дополнительную бизнес-валидацию
        if not prc.is_valid():
            return Response({"detail": "Токен недійсний або прострочений."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Меняем пароль
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Текущий код — в used
        prc.used = True
        prc.save(update_fields=["used"])

        # Остальные активные коды инвалидируем
        PasswordResetCode.objects.filter(
            user=user, used=False, expires_at__gt=dj_timezone.now()
        ).update(used=True)

        return Response({"ok": True}, status=status.HTTP_200_OK)


@login_required
@csrf_exempt
def admin_dashboard_view(request):
    return render(request, 'custom_admin/dashboard.html')
def _exclude_shadow_items(qs):
    """
    Удаляет PlaylistItem с шэдоу-треками (id начинается с '__').
    Работает корректно с FK через join.
    """
    try:
        return qs.exclude(track__id__startswith="__")
    except Exception:
        # на всякий случай — безопасный no-op, чтобы не уронить вью
        return qs


# =========================
# Helpers (urls / formatting / serialization)
# =========================

def _ensure_obj_duration_from_file(obj, file_attr: str, seconds_attr: str) -> bool:
    """
    Если у объекта нет длительности, а у FileField есть путь — считать длительность
    и сохранить в seconds_attr. Вернёт True, если поле было обновлено.
    """
    try:
        seconds = getattr(obj, seconds_attr, None) or 0
        f = getattr(obj, file_attr, None)
        if (not seconds) and f and getattr(f, "path", None):
            dur = _probe_duration_seconds(f.path)
            if dur and dur > 0:
                setattr(obj, seconds_attr, int(dur))
                obj.save(update_fields=[seconds_attr])
                return True
    except Exception:
        pass
    return False

def _shadow_track_ids() -> list[str]:
    """Вернёт список id шэдоу-треков (начинающихся на '__')."""
    return list(
        Track.objects.filter(id__startswith="__").values_list("id", flat=True)
    )

def _smart_tracks_count_for_playlist(p: Playlist) -> int:
    """
    Только для музыкальных плейлистов.
    Считаем без шэдоу-треков:
      1) прямые PlaylistItem
      2) fallback по albumid == title / id / slug(title)
      3) fallback по артисту
    """
    try:
        shadow = _shadow_track_ids()

        # 1) прямые элементы
        base_qs = PlaylistItem.objects.filter(playlist=p)
        if shadow:
            base_qs = base_qs.exclude(track_id__in=shadow)
        base = base_qs.count()
        if base:
            return base

        # 2) fallback по albumid
        title = (p.title or "").strip()
        patt  = r'^\s*' + re.escape(title) + r'\s*$'
        slugv = slugify(title)
        qs2 = Track.objects.filter(
            Q(albumid__iexact=title) |
            Q(albumid__iregex=patt)  |
            Q(albumid__iexact=str(p.pk)) |
            Q(albumid__iexact=slugv)
        )
        if shadow:
            qs2 = qs2.exclude(id__in=shadow)
        c = qs2.count()
        if c:
            return c

        # 3) fallback по артисту
        artist_id = ""
        try:
            if getattr(p, "artist", None):
                artist_id = str(p.artist.id or "")
        except Exception:
            pass

        if not artist_id:
            first_it_qs = (
                PlaylistItem.objects
                .filter(playlist=p)
                .select_related("track")
                .order_by("position", "id")
            )
            if shadow:
                first_it_qs = first_it_qs.exclude(track_id__in=shadow)
            first_it = first_it_qs.first()
            if first_it and first_it.track and first_it.track.artistid:
                artist_id = first_it.track.artistid

        if artist_id:
            qs3 = Track.objects.filter(artistid__iexact=artist_id)
            if shadow:
                qs3 = qs3.exclude(id__in=shadow)
            return qs3.count()

        return 0
    except Exception:
        # Любая неожиданность — лучше 0, чем 500
        return 0

def duration_label(seconds: int | None) -> str:
    s = int(seconds or 0)
    if s <= 0:
        return "0:00"
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"



def _abs_url(request, f) -> str:
    """
    Абсолютный URL для File/ImageField ИЛИ строкового пути/URL.
    Поддерживает:
    - FieldFile: .url / .name
    - str: http(s)://..., /abs/path, относительное имя (через MEDIA_URL)
    """
    try:
        if not f:
            return ""

        # FieldFile с .url
        u = getattr(f, "url", None)
        if u:
            return request.build_absolute_uri(u)

        # FieldFile только с .name
        name = getattr(f, "name", "")
        if name:
            return request.build_absolute_uri(urljoin(settings.MEDIA_URL, name))

        # Строка
        if isinstance(f, str):
            s = f.strip()
            if not s:
                return ""
            if s.startswith("http://") or s.startswith("https://"):
                return s
            if s.startswith("/"):
                return request.build_absolute_uri(s)
            return request.build_absolute_uri(urljoin(settings.MEDIA_URL, s))
    except Exception:
        pass
    return ""



def _cover_or_placeholder(request, filefield) -> str:
    """
    Возвращает абсолютный URL для cover; если не найден – ПУСТУЮ строку
    (чтобы фронт сам подставил дефолт, и не было 404).
    """
    u = _abs_url(request, filefield)
    if u:
        return u
    # если хочешь всё же плейсхолдер — убедись, что он существует
    # return request.build_absolute_uri(static('img/placeholder-cover.png'))
    return ""


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def _mmss_from_seconds(val):
    try:
        s = int(float(val or 0))
    except Exception:
        s = 0
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"


def fmt_time(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _to_int_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    if s.startswith("#"):
        s = s[1:]
    try:
        return int(s)
    except Exception:
        return None


def _probe_duration_seconds(path: str) -> int | None:
    """
    Пытаемся вытащить длительность аудио (секунды).
    Используем mutagen, если установлен. Если нет — просто молча вернём None.
    """
    try:
        from mutagen import File as MF  # type: ignore
        m = MF(path)
        if m and getattr(m, "info", None) and getattr(m.info, "length", None):
            return int(m.info.length)
    except Exception:
        pass
    return None


def _order_qs(qs, sort: str | None, order: str | None):
    if not sort:
        return qs
    order = (order or "asc").lower()
    allowed = {"created_at", "id", "time", "name", "position", "title"}
    if sort not in allowed:
        return qs
    sign = "-" if order == "desc" else ""
    try:
        return qs.order_by(f"{sign}{sort}")
    except Exception:
        # если поле отсутствует у данной модели — просто не сортируем
        return qs



def _limit_qs(qs, limit: str | None):
    try:
        n = int(limit or "")
        return qs[:max(0, n)]
    except Exception:
        return qs


# ---------- JSON builders ----------

def track_json(t: Track, request) -> dict:
    audio_abs = _abs_url(request, t.audio)
    cover_abs = _cover_or_placeholder(request, t.cover)

    # ← гарантированно попробуем посчитать и ПЕРЕЗАПИСАТЬ t.time
    _ensure_obj_duration_from_file(t, file_attr="audio", seconds_attr="time")

    stream_abs = ""
    if audio_abs:
        try:
            stream_abs = request.build_absolute_uri(reverse('stream_track', args=[t.id]))
        except Exception:
            stream_abs = ""

    # красивое имя артиста
    artist_display = t.artistid or ""
    try:
        ar = ArtistLinks.objects.filter(pk=t.artistid).only("name").first()
        if ar and ar.name:
            artist_display = ar.name
    except Exception:
        pass

    dur_sec = int(t.time or 0)

    return {
        "id": t.id,
        "name": t.name,
        "artistid": t.artistid or "",
        "artist_display": artist_display,
        "genreid": t.genreid or "",
        "albumid": t.albumid or "",
        "playsnum": str(t.playsnum or "0"),
        "adult": bool(t.adult),
        "time": dur_sec,                               # ← секунды
        "time_label": duration_label(dur_sec),         # ← 0:00 / mm:ss / hh:mm:ss
        "audio": audio_abs,
        "cover": cover_abs,
        "created_at": _iso(getattr(t, "created_at", None)),
        "audio_url": audio_abs,
        "cover_url": cover_abs,
        "stream_url": stream_abs,
    }

def _artist_name_by_id(aid: str) -> str:
    try:
        a = ArtistLinks.objects.filter(pk=aid).only("name").first()
        return a.name if a and a.name else ""
    except Exception:
        return ""

def _first_track_artist_name(p: Playlist) -> str:
    try:
        it = (PlaylistItem.objects
              .filter(playlist=p)
              .select_related("track")
              .order_by("position", "id")
              .first())
        if it and it.track and it.track.artistid:
            return _artist_name_by_id(it.track.artistid)
    except Exception:
        pass

def playlist_json(p, request):
    owner_user_id = ""
    if getattr(p, "owner_id", None):
        owner_user_id = str(p.owner_id)

    artist_owner_id = ""
    if getattr(p, "artist_id", None):
        artist_owner_id = str(p.artist_id)

    # NEW: читаем имя автора плейлиста
    artist_display = ""
    if artist_owner_id:
        artist_display = _artist_name_by_id(artist_owner_id)
    if not artist_display:
        artist_display = _first_track_artist_name(p)

    return {
        "id": str(p.id),
        "title": p.title,
        "description": p.description or "",
        "cover": _abs_url(request, getattr(p, "cover", None)),
        "owner_id": owner_user_id,
        "artist_id": artist_owner_id,
        "artist_display": artist_display,   # <-- ВАЖНО
        "created_at": getattr(p, "created_at", None).isoformat() if getattr(p, "created_at", None) else "",
    }

def playlist_item_json(it: PlaylistItem, request) -> dict:
    # плоский формат (как в типах фронта)
    return {
        "id": str(it.id),
        "playlist_id": str(it.playlist_id),
        "track": str(it.track_id),
        "position": str(it.position),
    }


def artist_json(a: ArtistLinks, request) -> dict:
    ls = (getattr(a, "listeners", None) or getattr(a, "listener", None) or "0")
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description or "",
        "photo": _abs_url(request, a.photo),         # абсолютный URL
        "listeners": str(ls),                        # единый ключ listeners
    }

from datetime import timezone as _tz
def probe_duration_seconds(file_field) -> int:
    """
    Возвращает длительность аудио в секундах.
    Работает для локального хранилища (file_field.path).
    Для S3 и т.п. придётся открывать stream через storage.open().
    """
    if not file_field:
        return 0
    # для FileSystemStorage есть .path
    path = getattr(file_field, "path", None)
    if not path:
        return 0
    try:
        mf = MutagenFile(path)
        if mf and getattr(mf, "info", None) and getattr(mf.info, "length", None):
            return int(round(mf.info.length))
    except Exception:
        pass
    return 0
from mutagen import File as MutagenFile
def duration_label(seconds: int) -> str:
    s = int(seconds or 0)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
def audiobook_json(a: AudioBook, request):
    created = getattr(a, "created_at", None) or datetime.now(_tz.utc)
    updated = getattr(a, "update_at", None) or created

    dur = int(a.duration_seconds or 0)
    if dur == 0 and a.audio_file:
        # пробуем считать длительность из файла
        dur = probe_duration_seconds(a.audio_file)
        if dur > 0:
            # кэшируем в БД, чтобы не считать каждый раз
            AudioBook.objects.filter(pk=a.pk).update(duration_seconds=dur)

    audio_abs = _abs_url(request, a.audio_file)
    cover_abs = _abs_url(request, a.cover_image)

    return {
        "id": a.id,
        "title": a.title,
        "author": a.author or "",
        "author_fk_id": str(getattr(a, "author_fk_id", "") or ""),
        "genreid": a.genreid or "",
        "playsnum": int(a.playsnum or 0),
        "adult": bool(a.adult),
        "duration_seconds": dur,
        "duration_label": duration_label(dur),
        "info": a.info or "",
        "chapter": int(a.chapter or 0),
        "audio_file": audio_abs,
        "cover_image": cover_abs,
        "created_at": _iso(created),
        "update_at": _iso(updated),
    }

def _norm_key(s: str | None) -> str:
    return (s or "").strip().lower()

def podcast_json(p: PodcastEpisode, request):
    created = getattr(p, "created_at", None) or datetime.now(_tz.utc)
    updated = getattr(p, "update_at", None) or created
    dur = int(p.duration_seconds or 0)
    audio_abs = _abs_url(request, p.audio_file)
    cover_abs = _abs_url(request, p.cover_image)

    # пытаемся получить имя из FK, иначе берём строковый host
    author_name = ""
    try:
        if getattr(p, "host_fk", None):
            author_name = p.host_fk.name or ""
    except Exception:
        pass
    if not author_name:
        author_name = p.host or ""

    # key для фронта: либо id FK, либо нормализованное имя
    host_key = ""
    if getattr(p, "host_fk_id", None):
        host_key = str(p.host_fk_id)
    else:
        host_key = _norm_key(author_name or p.host)

    return {
        "id": p.id,
        "title": p.title,
        "episode": int(p.episode or 0),
        "host": p.host or "",                       # как было
        "host_fk_id": str(getattr(p, "host_fk_id", "") or ""),
        "host_display": author_name,                # НОВОЕ — всегда корректное имя
        "host_key": host_key,                       # НОВОЕ — ключ для словаря артистов
        "genreid": p.genreid or "",
        "playsnum": int(p.playsnum or 0),
        "adult": bool(p.adult),
        "duration_seconds": dur,
        "duration_label": duration_label(dur),
        "info": p.info or "",
        "audio_file": audio_abs,
        "cover_image": cover_abs,
        "created_at": _iso(created),
        "update_at": _iso(updated),
    }



# =========================
# Audiobooks (LIST for front)
# =========================

@require_http_methods(["GET"])
def audiobooks_list(request):
    """
    По умолчанию для фронта → AudioBook[]
    Добавь ?wrap=1 чтобы вернуть {"success": True, "items": [...], ...} как раньше.
    """
    q = (request.GET.get("q") or "").strip()
    _sort  = (request.GET.get("_sort") or "").strip() or "created_at"
    _order = (request.GET.get("_order") or "desc").strip().lower()
    _limit = (request.GET.get("_limit") or "").strip()

    qs = AudioBook.objects.all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(genreid__icontains=q))

    artistid = (request.GET.get("artistid") or "").strip()
    if artistid:
        ab_fk = ArtistLinks.objects.filter(pk=artistid).first()
        qs = qs.filter(Q(author_fk=ab_fk) | Q(author__iexact=artistid)) if ab_fk else qs.filter(author__iexact=artistid)

    qs = _order_qs(qs, _sort, _order)
    qs = _limit_qs(qs, _limit)

    data = [audiobook_json(x, request) for x in qs]

    if (request.GET.get("wrap") or "").lower() in ("1", "true", "yes"):
        # обёртка для админских страниц
        paged = _paginate_qs(AudioBook.objects.all().order_by("-id"), request)
        data_wrapped = [audiobook_json(x, request) for x in paged["items"]]
        return JsonResponse({
            "success": True,
            "items": data_wrapped,
            "page": paged["page"],
            "page_size": paged["page_size"],
            "total": paged["total"],
            "total_pages": paged["total_pages"],
        })
    return JsonResponse(data, safe=False)


# =========================
# Tracks
# =========================

@csrf_exempt
@require_http_methods(["POST"])
def create_track(request):
    try:
        name     = (request.POST.get('name') or '').strip()
        track_id = (request.POST.get('track_id') or '').strip()
        artistid = (request.POST.get('artistid') or '').strip()
        albumid  = (request.POST.get('albumid') or '').strip() or None
        genreid  = (request.POST.get('genreid') or '').strip() or None

        if not name or not track_id or not artistid:
            return JsonResponse({'success': False, 'error': 'Name, Track ID, and Artist ID are required'}, status=400)
        if Track.objects.filter(pk=track_id).exists():
            return JsonResponse({'success': False, 'error': 'Track with this ID already exists'}, status=400)

        with transaction.atomic():
            track = Track.objects.create(
                id=track_id,
                name=name,
                artistid=artistid,
                albumid=albumid,
                genreid=genreid,
                playsnum='0',
                adult=False,
                time=0,
            )
            tf = request.FILES.get('track_file')
            ci = request.FILES.get('cover_image')
            if tf:
                track.audio = tf
            if ci:
                track.cover = ci
            track.save()

            # попробуем определить длительность
            if track.audio and getattr(track.audio, "path", None):
                dur = _probe_duration_seconds(track.audio.path)
                if dur:
                    track.time = dur
                    track.save(update_fields=["time"])

        return JsonResponse({'success': True, 'track': track_json(track, request)}, status=200)

    except IntegrityError as e:
        return JsonResponse({'success': False, 'error': 'DB integrity error: ' + str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def get_tracks(request):
    """
    Для фронта: возвращаем Track[].

    Понимаем ?albumid= как:
      - реальный плейлист (id / title / slug),
      - иначе — обычный фильтр по полю Track.albumid.
    Совместимость: ?wrap=1 вернёт старую обёртку с пагинацией.
    """
    try:
        albumid = (request.GET.get('albumid') or '').strip()
        _sort   = (request.GET.get('_sort') or '').strip()
        _order  = (request.GET.get('_order') or 'desc').strip().lower()
        _limit  = (request.GET.get('_limit') or '').strip()
        wrap    = (request.GET.get("wrap") or "").lower() in ("1","true","yes")

        def _apply_sort_and_limit(data: list[dict]) -> list[dict]:
            if _sort in {"created_at", "id", "time", "name"}:
                reverse = (_order == "desc")
                keyf = (lambda x: (x.get(_sort) or 0)) if _sort == "time" else (lambda x: (x.get(_sort) or ""))
                data.sort(key=keyf, reverse=reverse)
            if _limit.isdigit():
                return data[:int(_limit)]
            return data

        # ----- 1) albumid → реальный плейлист -----
        if albumid:
            raw = albumid
            pl = None
            data = []

            if raw.isdigit():
                pl = Playlist.objects.filter(pk=int(raw)).first()
            if pl is None:
                pl = Playlist.objects.filter(title__iexact=raw).first()
            if pl is None:
                want = slugify(raw)
                if hasattr(Playlist, "slug"):
                    pl = Playlist.objects.filter(slug=want).first()
                if pl is None:
                    for candidate in Playlist.objects.only("id", "title"):
                        if slugify(candidate.title or "") == want:
                            pl = candidate
                            break

            if pl is not None:
                # реальные элементы по position без шэдоу
                qs_items = (
                    PlaylistItem.objects
                    .filter(playlist_id=pl.pk)
                    .select_related("track")
                    .order_by("position", "id")
                )
                shadow_ids = _shadow_track_ids()
                if shadow_ids:
                    qs_items = qs_items.exclude(track_id__in=shadow_ids)

                data = [track_json(it.track, request) for it in qs_items if it.track]

                # fallback по albumid == title/id/slug
                if not data:
                    title = (pl.title or "").strip()
                    patt  = r'^\s*' + re.escape(title) + r'\s*$'
                    slugv = slugify(title)
                    qs = Track.objects.filter(
                        Q(albumid__iexact=title) |
                        Q(albumid__iregex=patt)   |
                        Q(albumid__iexact=str(pl.pk)) |
                        Q(albumid__iexact=slugv)
                    )
                    data = [track_json(t, request) for t in qs if not str(t.id).startswith("__")]

                # fallback по артисту
                if not data:
                    artist_id = ""
                    first_item_qs = (
                        PlaylistItem.objects
                        .filter(playlist=pl)
                        .select_related("track")
                        .order_by("position", "id")
                    )
                    if shadow_ids:
                        first_item_qs = first_item_qs.exclude(track_id__in=shadow_ids)
                    first_item = first_item_qs.first()

                    if first_item and first_item.track and first_item.track.artistid:
                        artist_id = first_item.track.artistid
                    else:
                        title = (pl.title or "").strip()
                        slugv = slugify(title)
                        t = (
                            Track.objects.filter(
                                Q(albumid__iexact=title) |
                                Q(albumid__iexact=str(pl.pk)) |
                                Q(albumid__iexact=slugv)
                            ).order_by("id").first()
                        )
                        if t and t.artistid:
                            artist_id = t.artistid

                    if artist_id:
                        qs = Track.objects.filter(artistid__iexact=artist_id)
                        data = [track_json(t, request) for t in qs if not str(t.id).startswith("__")]

                data = _apply_sort_and_limit(data)
                if wrap:
                    return JsonResponse({
                        'success': True,
                        'tracks': data,
                        'page': 1,
                        'page_size': len(data),
                        'total': len(data),
                        'total_pages': 1,
                    }, status=200)
                return JsonResponse(data, safe=False)

        # ----- 2) обычный режим -----
        qs = Track.objects.all()

        # date range
        start_s = request.GET.get('start')
        end_s   = request.GET.get('end')
        if (start_s or end_s) and hasattr(Track, 'created_at'):
            tz = get_current_timezone()
            if start_s:
                d = parse_date(start_s)
                if d:
                    qs = qs.filter(created_at__gte=make_aware(datetime.combine(d, time.min), tz))
            if end_s:
                d = parse_date(end_s)
                if d:
                    qs = qs.filter(created_at__lte=make_aware(datetime.combine(d, time.max), tz))

        # search
        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(id__icontains=q) |
                Q(artistid__icontains=q) |
                Q(albumid__icontains=q) |
                Q(genreid__icontains=q)
            )

        # exact filters
        for param in ('artistid', 'albumid', 'genreid'):
            val = (request.GET.get(param) or '').strip()
            if val:
                qs = qs.filter(**{f'{param}__iexact': val})

        adult_param = request.GET.get('adult')
        if adult_param in ('true', 'false'):
            qs = qs.filter(adult=(adult_param == 'true'))

        if request.GET.get('has_audio') in ('1','true','yes','on'):
            qs = qs.filter(audio__isnull=False).exclude(audio='')

        qs = _order_qs(qs, _sort or 'created_at', _order or 'desc')
        qs = _limit_qs(qs, _limit)

        if wrap:
            page = max(int(request.GET.get('page', 1)), 1)
            page_size = max(int(request.GET.get('page_size', 25)), 1)
            paginator = Paginator(qs, page_size)
            page = min(page, paginator.num_pages or 1)
            page_obj = paginator.page(page)
            data = [track_json(t, request) for t in page_obj.object_list]
            return JsonResponse({
                'success': True,
                'tracks': data,
                'page': page,
                'page_size': page_size,
                'total': paginator.count,
                'total_pages': paginator.num_pages,
            })

        data = [track_json(t, request) for t in qs]
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




@require_GET
def track_detail_simple(request, track_id: str):
    """
    GET /tracks/<id> → Track
    """
    t = Track.objects.filter(pk=track_id).first()
    if not t:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(track_json(t, request), status=200)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_track(request, track_id):
    try:
        track = Track.objects.get(id=track_id)
        track.delete()
        return JsonResponse({'success': True})
    except Track.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Track not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "PATCH", "PUT"])
def update_track(request, track_id):
    try:
        new_id = (request.POST.get("new_id") or "").strip()

        def take(key):
            return (request.POST.get(key) or "").strip() if key in request.POST else None

        def take_bool(key):
            if key not in request.POST:
                return None
            v = (request.POST.get(key) or "").strip().lower()
            return v in ("1","true","on","yes")

        patch = {
            "name":     take("name"),
            "artistid": take("artistid"),
            "albumid":  take("albumid"),
            "genreid":  take("genreid"),
            "tagsid":   take("tagsid"),
            "seqnum":   take("seqnum"),
            "info":     take("info"),
            "adult":    take_bool("adult"),   # <-- НОВОЕ
        }

        tf = request.FILES.get("track_file")
        cf = request.FILES.get("cover_image")

        with transaction.atomic():
            old = Track.objects.select_for_update().get(pk=track_id)

            # смена PK
            if new_id and new_id != track_id:
                if Track.objects.filter(pk=new_id).exists():
                    return JsonResponse({"success": False, "error": "Track with this ID already exists"}, status=400)

                new = Track(
                    id=new_id,
                    name=old.name, artistid=old.artistid, albumid=old.albumid, genreid=old.genreid,
                    playsnum=old.playsnum, adult=old.adult, time=old.time,
                    audio=old.audio, cover=old.cover,
                    tagsid=getattr(old, "tagsid", None),
                    seqnum=getattr(old, "seqnum", None),
                    info=getattr(old, "info", ""),
                )
                for f, v in patch.items():
                    if v is not None:
                        setattr(new, f, v or (False if f == "adult" else None))
                if tf: new.audio = tf
                if cf: new.cover = cf
                new.save()

                if tf and new.audio and getattr(new.audio, "path", None):
                    dur = _probe_duration_seconds(new.audio.path)
                    if dur:
                        new.time = dur
                        new.save(update_fields=["time"])

                PlaylistItem.objects.filter(track_id=track_id).update(track_id=new_id)
                old.delete()
                return JsonResponse({"success": True, "track": track_json(new, request)})

            # обычный апдейт
            for f, v in patch.items():
                if v is not None:
                    setattr(old, f, v or (False if f == "adult" else None))
            if tf:
                old.audio = tf
            if cf:
                old.cover = cf
            old.save()

            if tf and old.audio and getattr(old.audio, "path", None):
                dur = _probe_duration_seconds(old.audio.path)
                if dur:
                    old.time = dur
                    old.save(update_fields=["time"])

            return JsonResponse({"success": True, "track": track_json(old, request)})

    except Track.DoesNotExist:
        return JsonResponse({"success": False, "error": "Track not found"}, status=404)
    except IntegrityError as e:
        return JsonResponse({"success": False, "error": f"DB integrity error: {e}"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def _range_stream(file_path, start, end, chunk_size=8192):
    with open(file_path, 'rb') as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def stream_track(request, track_id):
    try:
        t = Track.objects.get(pk=track_id)
        if not t.audio:
            raise Http404("no audio")
        path = t.audio.path
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or 'audio/mpeg'

        rng = request.headers.get('Range') or request.META.get('HTTP_RANGE', "")
        if rng:
            m = re.match(r'bytes=(\d+)-(\d*)', rng)
            if not m:
                return FileResponse(open(path, 'rb'), content_type=ctype)
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            length = end - start + 1

            resp = StreamingHttpResponse(
                _range_stream(path, start, end),
                status=206, content_type=ctype
            )
            resp['Content-Length'] = str(length)
            resp['Content-Range'] = f'bytes {start}-{end}/{size}'
            resp['Accept-Ranges'] = 'bytes'
            return resp

        resp = FileResponse(open(path, 'rb'), content_type=ctype)
        resp['Content-Length'] = str(size)
        resp['Accept-Ranges'] = 'bytes'
        return resp
    except Track.DoesNotExist:
        raise Http404()


@csrf_exempt
def tracks_by_field(request, field, value=None):
    """
    Список треков по полю (artistid/albumid/genreid).
    По умолчанию → Track[] для фронта.
    Если ?wrap=1 — вернуть старую обёртку с items для админки.
    Дополнительно: если field=='albumid' и value — это плейлист (id или title),
    вернём треки из плейлиста.
    """
    field = (field or "").lower()
    if field not in {"albumid", "genreid", "artistid"}:
        return JsonResponse({"success": False, "error": "Unknown field"}, status=400)

    wrap = (request.GET.get("wrap") or "").lower() in ("1", "true", "yes")

    # --- Кейс плейлиста для albumid ---
    if field == "albumid" and value:
        raw = (value or "").strip()
        pl = None
        if raw.isdigit():
            pl = Playlist.objects.filter(pk=int(raw)).first()
        if pl is None:
            pl = Playlist.objects.filter(title__iexact=raw).first()

        if pl is not None:
            qs_items = (
                PlaylistItem.objects
                .filter(playlist_id=pl.pk)
                .select_related("track")
                .order_by("position", "id")
            )
            tracks = [track_json(it.track, request) for it in qs_items if it.track]
            if wrap:
                return JsonResponse({
                    "success": True,
                    "tracks": tracks,
                    "page": 1,
                    "page_size": len(tracks),
                    "total": len(tracks),
                    "total_pages": 1,
                })
            return JsonResponse(tracks, safe=False)

    # --- Обычный фильтр по полю модели Track ---
    qs = Track.objects.all()
    if value:
        qs = qs.filter(**{f"{field}__iexact": value})

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(id__icontains=q))

    _sort  = (request.GET.get("_sort") or "").strip() or "created_at"
    _order = (request.GET.get("_order") or "desc").strip().lower()
    qs = _order_qs(qs, _sort, _order)

    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except Exception:
        page = 1
    try:
        page_size = max(int(request.GET.get("page_size", 50)), 1)
    except Exception:
        page_size = 50

    p = Paginator(qs, page_size)
    page = min(page, p.num_pages or 1)
    page_obj = p.page(page)

    if wrap:
        # старый формат для админки
        items = [{
            "id": t.id,
            "name": t.name,
            "artistid": t.artistid,
            "albumid": t.albumid or "",
            "genreid": t.genreid or "",
            "field": field,
            "field_value": getattr(t, field) or "",
        } for t in page_obj.object_list]
        return JsonResponse({
            "success": True,
            "items": items,
            "fields": ["name", "id", field],
            "field": field,
            "value": value or "",
            "page": page,
            "page_size": page_size,
            "total": p.count,
            "total_pages": p.num_pages,
        })

    # Новый формат для фронта — массив треков
    data = [track_json(t, request) for t in page_obj.object_list]
    return JsonResponse(data, safe=False)


# =========================
# Customers
# =========================
def _build_customers_payload(request):
    qs = User.objects.all().order_by('-id').select_related("profile")

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(email__icontains=q) |
            Q(full_name__icontains=q) |
            Q(profile__display_name__icontains=q) |
            Q(profile__city__icontains=q)
        )

    role = (request.GET.get('role') or '').strip().lower()
    if role == 'admin':
        qs = qs.filter(is_admin=True)
    elif role == 'staff':
        qs = qs.filter(is_admin=False, is_staff=True)
    elif role == 'client':
        qs = qs.filter(is_admin=False, is_staff=False)

    try:
        page = max(int(request.GET.get('page', 1)), 1)
    except Exception:
        page = 1
    try:
        page_size = max(int(request.GET.get('page_size', 10)), 1)
    except Exception:
        page_size = 10

    total = qs.count()
    items_qs = qs[(page-1)*page_size : page*page_size]

    with_profile = (request.GET.get('with_profile') or '1').lower() in ('1','true','yes')

    data = []
    for u in items_qs:
        row = {
            'id': u.id,
            'email': u.email,
            'full_name': (u.full_name or "") or (u.email.split('@')[0] if u.email else ""),
            'is_admin': bool(u.is_admin),
            'is_staff': bool(u.is_staff),
            'is_client': bool(u.is_client),
            'role': 'admin' if u.is_admin else ('staff' if u.is_staff else 'client'),
        }
        if with_profile:
            p = getattr(u, 'profile', None)
            row['profile'] = {
                'display_name': getattr(p, 'display_name', '') if p else '',
                'country_code': getattr(p, 'country_code', '') if p else '',
                'city': getattr(p, 'city', '') if p else '',
                'date_of_birth': getattr(p, 'date_of_birth', None) if p else None,
                'role': getattr(p, 'role', 'user') if p else 'user',
            }
        data.append(row)

    return {
        'success': True,
        'items': data,
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': (total + page_size - 1) // page_size,
    }

# cookie-сессии (админка)
@login_required(login_url='/api/auth/')
@require_GET
def get_customers_session(request):
    return JsonResponse(_build_customers_payload(request), status=200)

# JWT и/или сессии (для React и админки)
@api_view(['GET'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_customers_api(request):
    return Response(_build_customers_payload(request), status=200)

# Create / Update / Delete — тоже пускаем и по сессии, и по JWT
@api_view(['POST'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def create_customer(request):
    email = (request.POST.get('email') or '').strip().lower()
    full_name = (request.POST.get('full_name') or '').strip()
    account_role = (request.POST.get('role') or 'client').strip().lower()

    display_name  = (request.POST.get('display_name') or '').strip()
    country_code  = (request.POST.get('country_code') or '').strip().upper()[:2]
    city          = (request.POST.get('city') or '').strip()
    profile_role  = (request.POST.get('profile_role') or 'user').strip()
    dob_str       = (request.POST.get('date_of_birth') or '').strip()

    password = (request.POST.get('password') or '').strip()
    if not email or not password:
        return Response({'success': False, 'error': 'Email and password are required'}, status=400)
    if User.objects.filter(email=email).exists():
        return Response({'success': False, 'error': 'Email already exists'}, status=400)

    from datetime import date
    dob = None
    if dob_str:
        try:
            y, m, d = map(int, dob_str.split('-'))
            dob = date(y, m, d)
        except Exception:
            return Response({'success': False, 'error': 'Invalid date_of_birth'}, status=400)

    with transaction.atomic():
        u = User.objects.create_user(email=email, password=password, full_name=full_name or "")
        u.is_admin = (account_role == 'admin')
        u.is_staff = (account_role in ('admin', 'staff'))
        u.is_client = not u.is_admin and not u.is_staff
        u.save()

        Profile.objects.create(
            user=u,
            display_name = display_name or full_name or email,
            country_code = country_code,
            city = city,
            role = profile_role,
            date_of_birth = dob,
        )

    return Response({'success': True, 'id': u.id}, status=200)

@api_view(['POST','PUT','PATCH'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def update_customer(request, user_id):
    try:
        u = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return Response({'success': False, 'error': 'User not found'}, status=404)

    email = (request.POST.get('email') or '').strip().lower() if 'email' in request.POST else None
    full_name = (request.POST.get('full_name') or '').strip() if 'full_name' in request.POST else None
    account_role = (request.POST.get('role') or '').strip().lower() if 'role' in request.POST else None
    password = (request.POST.get('password') or '').strip() if 'password' in request.POST else None

    pd = {}
    if 'display_name' in request.POST: pd['display_name'] = (request.POST['display_name'] or '').strip()
    if 'country_code' in request.POST: pd['country_code'] = (request.POST['country_code'] or '').strip().upper()[:2]
    if 'city' in request.POST: pd['city'] = (request.POST['city'] or '').strip()
    if 'profile_role' in request.POST: pd['role'] = (request.POST['profile_role'] or 'user').strip()

    if 'date_of_birth' in request.POST:
        dob_str = (request.POST.get('date_of_birth') or '').strip()
        from datetime import date
        if dob_str:
            try:
                y, m, d = map(int, dob_str.split('-'))
                pd['date_of_birth'] = date(y, m, d)
            except Exception:
                return Response({'success': False, 'error': 'Invalid date_of_birth'}, status=400)
        else:
            pd['date_of_birth'] = None

    if email and email != u.email:
        if User.objects.filter(email=email).exclude(pk=u.pk).exists():
            return Response({'success': False, 'error': 'Email already exists'}, status=400)
        u.email = email
    if full_name is not None:
        u.full_name = full_name
    if account_role:
        u.is_admin = (account_role == 'admin')
        u.is_staff = (account_role in ('admin','staff'))
        u.is_client = not u.is_admin and not u.is_staff
    if password:
        u.set_password(password)

    u.save()
    if pd:
        Profile.objects.update_or_create(user=u, defaults=pd)

    return Response({'success': True}, status=200)

@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def delete_customer(request, user_id):
    try:
        u = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'success': False, 'error': 'User not found'}, status=404)
    u.delete()
    return Response({'success': True}, status=200)

@api_view(['POST'])
@authentication_classes([SessionAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def bulk_delete_customers(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    ids = payload.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return Response({'success': False, 'error': 'ids must be non-empty list'}, status=400)
    deleted = User.objects.filter(id__in=ids).delete()[0]
    return Response({'success': True, 'deleted': deleted}, status=200)

# =========================
# Playlists
# =========================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def playlists_index(request):
    if request.method == "GET":
        return list_playlists(request)

    try:
        payload = json.loads((request.body or b"").decode("utf-8") or "{}") \
                  if request.content_type and "application/json" in request.content_type \
                  else request.POST.dict()
    except Exception:
        payload = {}

    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    if not title:
        return JsonResponse({"success": False, "error": "Title is required"}, status=400)

    # анти-дубликат по title (+ owner, если он есть и юзер залогинен)
    qs = Playlist.objects.filter(title__iexact=title)
    if hasattr(Playlist, "owner") and getattr(request.user, "is_authenticated", False):
        qs = qs.filter(owner=request.user)

    ex = qs.first()
    if ex:
        return JsonResponse(playlist_json(ex, request), status=200)

    with transaction.atomic():
        kwargs = {"title": title, "description": description}
        if hasattr(Playlist, "owner"):
            f = Playlist._meta.get_field("owner")
            if getattr(f, "null", True):
                kwargs["owner"] = request.user if getattr(request.user, "is_authenticated", False) else None
            elif getattr(request.user, "is_authenticated", False):
                kwargs["owner"] = request.user
        pl = Playlist.objects.create(**kwargs)

    return JsonResponse(playlist_json(pl, request), status=201)

@require_http_methods(["GET"])
def list_playlists(request):
    try:
        qs = Playlist.objects.all()

        # --- совместимость с json-server: owner_id может быть строкой вроде "a126"
        owner_param = (request.GET.get("owner_id") or "").strip()
        if owner_param:
            if owner_param.isdigit():
                qs = qs.filter(owner_id=int(owner_param))
            else:
                # строковые userId из моков игнорируем, чтобы не падать (поиск пойдёт по title)
                pass

        title = (request.GET.get("title") or "").strip()
        if title:
            qs = qs.filter(title__iexact=title)

        _sort  = (request.GET.get("_sort") or "").strip() or "created_at"
        _order = (request.GET.get("_order") or "desc").strip().lower()
        _limit = (request.GET.get("_limit") or "").strip()
        with_counts = (request.GET.get("with_counts") or "1").lower() in ("1","true","yes")
        wrap = (request.GET.get("wrap") or "").lower() in ("1","true","yes")

        qs = _order_qs(qs, _sort, _order)
        qs = _limit_qs(qs, _limit)

        # базовый подсчёт только по PlaylistItem (без шэдоу)
        counts = {}
        if with_counts or wrap:
            shadow_ids = _shadow_track_ids()
            base_qs = PlaylistItem.objects.all()
            if shadow_ids:
                base_qs = base_qs.exclude(track_id__in=shadow_ids)
            counts_qs = base_qs.values('playlist_id').annotate(c=Count('id'))
            counts = {row['playlist_id']: row['c'] for row in counts_qs}

        FAV_TITLES_SKIP_SMART = {
            'улюблені подксати',
            'улюблені аудіокниги',
            'улюблені виконавці',
            'улюблені автори',
        }

        def build(p: Playlist):
            obj = playlist_json(p, request)
            if with_counts:
                base = int(counts.get(p.pk, 0))
                if base > 0:
                    obj["tracks_count"] = base
                else:
                    # «Любимые подкасты/аудиокниги/исполнители» не считаем умно — 0
                    t = (p.title or "").strip().lower()
                    if t in FAV_TITLES_SKIP_SMART:
                        obj["tracks_count"] = 0
                    else:
                        # безопасный «умный» подсчёт
                        obj["tracks_count"] = _smart_tracks_count_for_playlist(p)
            return obj

        if wrap:
            page      = max(int(request.GET.get('page', 1)), 1)
            page_size = max(int(request.GET.get('page_size', 50)), 1)
            total     = Playlist.objects.count()
            start, end = (page - 1) * page_size, (page * page_size)
            items = [build(p) for p in Playlist.objects.all()[start:end]]
            return JsonResponse({
                'success': True,
                'items': items,
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size,
            }, status=200)

        data = [build(p) for p in qs]
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



@csrf_exempt
@require_http_methods(["POST"])
def create_playlist(request):
    try:
        if request.content_type and "application/json" in (request.content_type or ""):
            try:
                payload = json.loads((request.body or b"").decode("utf-8") or "{}")
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Bad JSON: {e}'}, status=400)
            title       = (payload.get('title') or '').strip()
            description = (payload.get('description') or '').strip()
            raw         = payload.get('tracks_json') or '[]'
        else:
            title       = (request.POST.get('title') or '').strip()
            description = (request.POST.get('description') or '').strip()
            raw         = request.POST.get('tracks_json') or '[]'

        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'}, status=400)

        qs = Playlist.objects.filter(title__iexact=title)
        if hasattr(Playlist, "owner") and getattr(request.user, "is_authenticated", False):
            qs = qs.filter(owner=request.user)
        ex = qs.first()
        if ex:
            return JsonResponse(playlist_json(ex, request), status=200)

        try:
            parsed = json.loads(raw)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'tracks_json is not valid JSON: {e}'}, status=400)

        incoming = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    incoming.append(str(item.get("id") or "").strip())
                else:
                    incoming.append(str(item).strip())

        # Только настоящие Track (без префикса "__")
        real_track_ids: list[str] = []
        for rid in incoming:
            t = Track.objects.filter(pk=rid).first()
            if t and not str(t.pk).startswith("__"):
                real_track_ids.append(t.pk)

        seen, ordered_ids = set(), []
        for tid in real_track_ids:
            if tid not in seen:
                seen.add(tid)
                ordered_ids.append(tid)

        with transaction.atomic():
            kwargs = {"title": title, "description": description}
            if hasattr(Playlist, "owner"):
                f = Playlist._meta.get_field("owner")
                is_auth = getattr(request.user, "is_authenticated", False)
                if getattr(f, "null", True):
                    kwargs["owner"] = request.user if is_auth else None
                elif is_auth:
                    kwargs["owner"] = request.user

            pl = Playlist.objects.create(**kwargs)

            if (f := (request.FILES.get('cover') if not (request.content_type or "").startswith("application/json") else None)):
                pl.cover = f
                pl.save()

            if ordered_ids:
                tmap = {t.pk: t for t in Track.objects.filter(pk__in=ordered_ids)}
                pos = 0
                bulk = []
                for tid in ordered_ids:
                    t = tmap.get(tid)
                    if t:
                        bulk.append(PlaylistItem(playlist=pl, track=t, position=pos))
                        pos += 1
                if bulk:
                    PlaylistItem.objects.bulk_create(bulk)

        return JsonResponse({'success': True, 'playlist': playlist_json(pl, request)}, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'create_playlist: {e}'}, status=500)



from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_http_methods(["POST", "PATCH", "PUT"])
def update_playlist(request, pl_id: int):
    try:
        pl = Playlist.objects.get(pk=pl_id)
    except Playlist.DoesNotExist:
        return JsonResponse({"success": False, "error": "Playlist not found"}, status=404)

    if hasattr(Playlist, "owner"):
        is_auth = getattr(request.user, "is_authenticated", False)
        is_super = bool(is_auth and getattr(request.user, "is_superuser", False))
        if pl.owner and not (is_super or (is_auth and request.user == pl.owner)):
            return JsonResponse({"success": False, "error": "Forbidden"}, status=403)

    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if title:
        pl.title = title
    if "description" in request.POST:
        pl.description = description
    if "cover" in request.FILES:
        pl.cover = request.FILES["cover"]

    if "tracks_json" in request.POST:
        try:
            parsed = json.loads(request.POST.get("tracks_json") or "[]")
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Bad tracks_json: {e}"}, status=400)

        incoming = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    incoming.append(str(item.get("id") or "").strip())
                else:
                    incoming.append(str(item).strip())

        real_track_ids: list[str] = []
        for rid in incoming:
            t = Track.objects.filter(pk=rid).first()
            if t and not str(t.pk).startswith("__"):
                real_track_ids.append(t.pk)

        seen, ordered_ids = set(), []
        for tid in real_track_ids:
            if tid not in seen:
                seen.add(tid)
                ordered_ids.append(tid)

        PlaylistItem.objects.filter(playlist=pl).delete()
        if ordered_ids:
            tmap = {t.pk: t for t in Track.objects.filter(pk__in=ordered_ids)}
            pos = 0
            for tid in ordered_ids:
                t = tmap.get(tid)
                if t:
                    PlaylistItem.objects.create(playlist=pl, track=t, position=pos)
                    pos += 1

    pl.save()
    return JsonResponse({"success": True, "playlist": playlist_json(pl, request)})


@require_http_methods(["DELETE"])
def delete_playlist(request, pl_id):
    try:
        # админам/персоналу позволяем удалять любые
        if any([
            getattr(request.user, "is_superuser", False),
            getattr(request.user, "is_staff", False),
            getattr(request.user, "is_admin", False),
        ]):
            pl = Playlist.objects.get(pk=pl_id)
        elif hasattr(Playlist, "owner") and getattr(request.user, "is_authenticated", False):
            # обычный пользователь – только свои
            pl = Playlist.objects.get(pk=pl_id, owner=request.user)
        else:
            # аноним – удаляем по pk (актуально для мусора, созданного анонимно)
            pl = Playlist.objects.get(pk=pl_id)

        pl.delete()
        return JsonResponse({'success': True})
    except Playlist.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Playlist not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def playlist_detail(request, pl_id: str):
    """
    GET /api/playlists/<pl_id>/?full=1
    pl_id: числовой PK, точное имя (case-insensitive) или slug(title).
    Если не найдено и ?virtual=1 — вернём «виртуальный» плейлист по артисту.
    """
    raw = (pl_id or "").strip()
    pl = None

    # 1) по числовому id
    if raw.isdigit():
        pl = Playlist.objects.filter(pk=int(raw)).first()

    # 2) по title
    if pl is None:
        pl = Playlist.objects.filter(title__iexact=raw).first()

    # 3) по slug(title)
    if pl is None:
        want = slugify(raw)
        if hasattr(Playlist, "slug"):
            pl = Playlist.objects.filter(slug=want).first()
        if pl is None:
            for candidate in Playlist.objects.only("id", "title"):
                if slugify(candidate.title or "") == want:
                    pl = candidate
                    break

    # 4) виртуальный плейлист по артисту (если включено)
    virtual_on = (request.GET.get("virtual") or "1").lower() in ("1", "true", "yes")
    if pl is None and virtual_on:
        tr_qs = Track.objects.filter(
            Q(artistid__iexact=raw)
        ).order_by("-created_at" if hasattr(Track, "created_at") else "-id")
        tracks = [track_json(t, request) for t in tr_qs]
        payload = {
            "id": raw,
            "title": raw,
            "description": "Автоплейлист по артисту",
            "cover": "",
            "owner_id": raw,
            "created_at": "",
            "tracks": tracks,
            "tracks_count": len(tracks),
        }
        return JsonResponse(payload, status=200)

    if pl is None:
        return JsonResponse({"success": False, "error": "Playlist not found"}, status=404)

    # обычный payload (без треков)
    payload = playlist_json(pl, request)

    # Заполним owner_id (артист плейлиста)
    if not payload.get("owner_id"):
        artist_id = ""
        first_item_qs = (
            PlaylistItem.objects
            .filter(playlist=pl)
            .select_related("track")
            .order_by("position", "id")
        )
        first_item_qs = _exclude_shadow_items(first_item_qs)  # <-- фикс
        first_it = first_item_qs.first()
        if first_it and first_it.track and first_it.track.artistid:
            artist_id = first_it.track.artistid
        else:
            title = (pl.title or "").strip()
            slug_ = slugify(title)
            t = (
                Track.objects.filter(
                    Q(albumid__iexact=title) |
                    Q(albumid__iexact=str(pl.pk)) |
                    Q(albumid__iexact=slug_)
                )
                .order_by("id")
                .first()
            )
            if t and t.artistid:
                artist_id = t.artistid

        if artist_id:
            payload["owner_id"] = artist_id
            payload["artist_id"] = artist_id

    # ?full=1 → приложить треки
    if (request.GET.get("full") or "").lower() in ("1", "true", "yes"):
        items_qs = (
            PlaylistItem.objects
            .filter(playlist=pl)
            .select_related("track")
            .order_by("position", "id")
        )
        items_qs = _exclude_shadow_items(items_qs)  # <-- фикс
        tracks = [track_json(it.track, request) for it in items_qs if it.track]

        if not tracks:
            # fallback 1: по albumid == title/id/slug
            title = (pl.title or "").strip()
            patt  = r'^\s*' + re.escape(title) + r'\s*$'
            slug_ = slugify(title)
            tr_qs = Track.objects.filter(
                Q(albumid__iexact=title) |
                Q(albumid__iregex=patt)  |
                Q(albumid__iexact=str(pl.pk)) |
                Q(albumid__iexact=slug_)
            ).order_by("created_at" if hasattr(Track, "created_at") else "id", "id")
            # на всякий случай — исключим шэдоу и тут
            tr_qs = tr_qs.exclude(id__startswith="__")
            tracks = [track_json(t, request) for t in tr_qs]

        if not payload.get("artist_display"):
            aid = (payload.get("artist_id") or payload.get("owner_id") or "").strip()
            name = _artist_name_by_id(aid) if aid else ""
            if not name and (request.GET.get("full") or "").lower() in ("1","true","yes"):
                # если отдали треки — возьмём артиста первого трека
                name = ""
                try:
                    if payload.get("tracks"):
                        first = payload["tracks"][0]
                        aid2 = str(first.get("artistid") or "")
                        if aid2:
                            name = _artist_name_by_id(aid2)
                except Exception:
                    pass
            payload["artist_display"] = name
        payload["tracks"] = tracks
        payload["tracks_count"] = len(tracks)

    return JsonResponse(payload, status=200)



@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def playlist_items(request, pl_id: str | None = None):
    # ---------- POST ----------
    if request.method == "POST":
        # payload
        if request.content_type and "application/json" in (request.content_type or ""):
            try:
                body = json.loads(request.body.decode("utf-8")) or {}
            except Exception:
                body = {}
            raw_pl = str(body.get("playlist_id") or "").strip()
            raw_tr = str(body.get("track") or "").strip()
            pos_in = str(body.get("position") or "").strip()
        else:
            raw_pl = (request.POST.get("playlist_id") or "").strip()
            raw_tr = (request.POST.get("track") or "").strip()
            pos_in = (request.POST.get("position") or "").strip()

        # найти плейлист по id/title/slug
        pl = None
        if raw_pl.isdigit():
            pl = Playlist.objects.filter(pk=int(raw_pl)).first()
        if pl is None:
            pl = Playlist.objects.filter(title__iexact=raw_pl).first()
        if pl is None:
            want = slugify(raw_pl)
            for p in Playlist.objects.only("id", "title"):
                if slugify(p.title or "") == want:
                    pl = p
                    break
        if pl is None:
            return JsonResponse({"success": False, "error": "playlist not found"}, status=404)

        # --- резолв входной сущности в Track (включая shadow) ---
        t: Track | None = None
        tr_in = raw_tr  # что прислали фронтом
        # 1) если это уже настоящий Track id
        t = Track.objects.filter(pk=tr_in).first()

        # 2) если это префиксованные id — снимаем префикс и создаём shadow
        if not t and tr_in.startswith("__pc_"):
            base = tr_in[5:]
            pc = None
            if base.isdigit():
                pc = PodcastEpisode.objects.filter(pk=int(base)).first()
            else:
                pc = PodcastEpisode.objects.filter(pk=base).first()
            if pc:
                t = _ensure_shadow_track_from_pc(pc)

        if not t and tr_in.startswith("__ab_"):
            base = tr_in[5:]
            ab = None
            if base.isdigit():
                ab = AudioBook.objects.filter(pk=int(base)).first()
            else:
                ab = AudioBook.objects.filter(pk=base).first()
            if ab:
                t = _ensure_shadow_track_from_ab(ab)

        if not t and tr_in.startswith("__ar_"):
            base = tr_in[5:]
            ar = ArtistLinks.objects.filter(pk=base).first()
            if ar:
                t = _ensure_shadow_track_from_ar(ar)

        # 3) «сырой» числовой id → пробуем как аб/подкаст (создаём shadow)
        if not t and tr_in.isdigit():
            ab = AudioBook.objects.filter(pk=int(tr_in)).first()
            if ab:
                t = _ensure_shadow_track_from_ab(ab)
            else:
                pc = PodcastEpisode.objects.filter(pk=int(tr_in)).first()
                if pc:
                    t = _ensure_shadow_track_from_pc(pc)

        # 4) «сырой» id артиста → создаём shadow
        if not t:
            ar = ArtistLinks.objects.filter(pk=tr_in).first()
            if ar:
                t = _ensure_shadow_track_from_ar(ar)

        # 5) В крайнем случае ещё раз проверим, вдруг shadow уже есть
        if not t and (tr_in.startswith("__ab_") or tr_in.startswith("__pc_") or tr_in.startswith("__ar_")):
            t = Track.objects.filter(pk=tr_in).first()

        if not t:
            return JsonResponse({"success": False, "error": "track entity not resolvable"}, status=400)

        # --- проверка дубликата с учётом shadow ---
        shadow_ids = [t.pk]

        # если пришёл сырой числовой id — добавим возможные зеркала
        if tr_in.isdigit():
            shadow_ids += [f"__ab_{tr_in}", f"__pc_{tr_in}"]

        # если пришёл id артиста (сырой или с префиксом) — учитываем artist-зеркало
        if tr_in.startswith("__ar_"):
            shadow_ids.append(tr_in)  # уже shadow
        elif ArtistLinks.objects.filter(pk=tr_in).exists():
            shadow_ids.append(f"__ar_{tr_in}")

        exists = PlaylistItem.objects.filter(playlist=pl, track_id__in=shadow_ids).first()
        if exists:
            return JsonResponse({
                "id": str(exists.id),
                "playlist_id": str(exists.playlist_id),
                "track": str(exists.track_id),
                "position": str(exists.position),
            })

        # --- позиция ---
        try:
            position = int(pos_in) if pos_in else None
        except Exception:
            position = None
        if position is None:
            last = (
                PlaylistItem.objects.filter(playlist=pl)
                .aggregate(mx=Max("position"))
                .get("mx") or 0
            )
            position = int(last) + 1

        # создать элемент
        it = PlaylistItem.objects.create(playlist=pl, track=t, position=position)
        return JsonResponse({
            "id": str(it.id),
            "playlist_id": str(it.playlist_id),
            "track": str(it.track_id),
            "position": str(it.position),
        })

    # ---------- DELETE ----------
    if request.method == "DELETE":
        item_id = (request.GET.get("id") or pl_id or "").strip()
        if not item_id:
            return JsonResponse({"success": False, "error": "id required"}, status=400)
        it = PlaylistItem.objects.filter(pk=item_id).first()
        if not it:
            return JsonResponse({"success": False, "error": "not found"}, status=404)
        it.delete()
        return JsonResponse({"success": True})

    # ---------- GET ----------
    raw = (request.GET.get("playlist_id") or request.GET.get("playlistId") or pl_id or "").strip()
    track_filter = (request.GET.get("track") or "").strip()
    if not raw:
        return JsonResponse([], safe=False)

    pl = None
    if raw.isdigit():
        pl = Playlist.objects.filter(pk=int(raw)).first()
    if pl is None:
        pl = Playlist.objects.filter(title__iexact=raw).first()
    if pl is None:
        want = slugify(raw)
        for p in Playlist.objects.only("id", "title"):
            if slugify(p.title or "") == want:
                pl = p
                break
    if not pl:
        return JsonResponse([], safe=False)

    qs = (
        PlaylistItem.objects
        .filter(playlist=pl)
        .select_related("track")
        .order_by("position", "id")
    )

    # shadow скрываем только для не-«Любимых …»
    pl_title_lc = (pl.title or "").strip().lower()
    is_favorites = pl_title_lc.startswith("любимые") or pl_title_lc.startswith("улюблен")
    if not is_favorites:
        shadow_ids_all = _shadow_track_ids()
        if shadow_ids_all:
            qs = qs.exclude(track_id__in=shadow_ids_all)

    # фильтр по track: учитываем все зеркала, включая __ar_ для числовых и строковых id
    if track_filter:
        keys = [track_filter]
        if track_filter.isdigit():
            keys += [f"__ab_{track_filter}", f"__pc_{track_filter}"]
        # и для артистов (даже если id числовой/строковый)
        if track_filter.startswith("__ar_"):
            keys.append(track_filter)
        elif ArtistLinks.objects.filter(pk=track_filter).exists():
            keys.append(f"__ar_{track_filter}")
        qs = qs.filter(track_id__in=keys)

    items = []
    for it in qs:
        tid_full = str(it.track_id)
        kind = "tr"; body = tid_full
        if tid_full.startswith("__ab_"): kind, body = "ab", tid_full[5:]
        elif tid_full.startswith("__pc_"): kind, body = "pc", tid_full[5:]
        elif tid_full.startswith("__ar_"): kind, body = "ar", tid_full[5:]

        items.append({
            "id": str(it.id),
            "playlist_id": str(it.playlist_id),
            "track": tid_full,
            "position": str(it.position),
            "entity_kind": kind,
            "entity_id": body,
        })

    return JsonResponse(items, safe=False)




# =========================
# Audiobooks (CRUD)
# =========================

@csrf_exempt
@require_http_methods(["POST"])
def audiobook_create(request):
    obj = AudioBook(
        title   = (request.POST.get("title") or "").strip(),
        author  = (request.POST.get("author") or "").strip(),
        genreid = (request.POST.get("genreid") or "").strip(),
        info    = (request.POST.get("info") or "").strip(),
        adult   = (request.POST.get("adult") in ("true","1","on","yes")),
    )
    obj.chapter = _to_int_or_none(request.POST.get("chapter"))
    obj.duration_seconds = _to_int_or_none(request.POST.get("duration_seconds"))

    if request.FILES.get("audio_file"): obj.audio_file = request.FILES["audio_file"]
    if request.FILES.get("cover_image"): obj.cover_image = request.FILES["cover_image"]
    obj.save()
    return JsonResponse({"success": True, "audiobook": audiobook_json(obj, request)})


@csrf_exempt
@require_http_methods(["POST","PATCH","PUT"])
def audiobook_update(request, pk: int):
    try:
        obj = AudioBook.objects.get(pk=pk)
    except AudioBook.DoesNotExist:
        return JsonResponse({"success": False, "error": "not found"}, status=404)

    for fld in ["title","author","genreid","info"]:
        if fld in request.POST:
            setattr(obj, fld, (request.POST.get(fld) or "").strip())

    if "adult" in request.POST:
        obj.adult = (request.POST.get("adult") in ("true","1","on","yes"))
    if "chapter" in request.POST:
        obj.chapter = _to_int_or_none(request.POST.get("chapter"))
    if "duration_seconds" in request.POST:
        obj.duration_seconds = _to_int_or_none(request.POST.get("duration_seconds"))

    if request.FILES.get("audio_file"): obj.audio_file = request.FILES["audio_file"]
    if request.FILES.get("cover_image"): obj.cover_image = request.FILES["cover_image"]

    obj.save()
    return JsonResponse({"success": True, "audiobook": audiobook_json(obj, request)})


@csrf_exempt
@require_http_methods(["DELETE"])
def audiobook_delete(request, pk: int):
    try:
        obj = AudioBook.objects.get(pk=pk)
    except AudioBook.DoesNotExist:
        return JsonResponse({"success": False, "error": "not found"}, status=404)
    obj.delete()
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def audiobooks_bulk_delete(request):
    try:
        ids = json.loads(request.body.decode("utf-8")).get("ids", [])
    except Exception:
        ids = []
    qs = AudioBook.objects.filter(pk__in=ids)
    deleted = qs.count()
    qs.delete()
    return JsonResponse({"success": True, "deleted": deleted})


# =========================
# Podcasts
# =========================

@require_http_methods(["GET"])
def podcasts_list(request):
    """
    По умолчанию → PodcastEpisode[] (для фронта).
    ?wrap=1 — вернуть старую обёртку с пагинацией.
    """
    q = (request.GET.get("q") or "").strip()
    _sort  = (request.GET.get("_sort") or "").strip() or "created_at"
    _order = (request.GET.get("_order") or "desc").strip().lower()
    _limit = (request.GET.get("_limit") or "").strip()

    qs = PodcastEpisode.objects.all()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(host__icontains=q) |
            Q(genreid__icontains=q)
        )
    artistid = (request.GET.get("artistid") or "").strip()
    if artistid:
        pc_fk = ArtistLinks.objects.filter(pk=artistid).first()
        qs = qs.filter(Q(host_fk=pc_fk) | Q(host__iexact=artistid)) if pc_fk else qs.filter(host__iexact=artistid)

    qs = _order_qs(qs, _sort, _order)
    qs = _limit_qs(qs, _limit)

    if (request.GET.get("wrap") or "").lower() in ("1","true","yes"):
        paged = _paginate_qs(PodcastEpisode.objects.all().order_by("-id"), request)
        data = [podcast_json(x, request) for x in paged["items"]]
        return JsonResponse({
            "success": True,
            "items": data,
            "page": paged["page"],
            "page_size": paged["page_size"],
            "total": paged["total"],
            "total_pages": paged["total_pages"],
        })

    data = [podcast_json(x, request) for x in qs]
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def podcastepisode_detail_simple(request, pk: int):
    p = PodcastEpisode.objects.filter(pk=pk).first()
    if not p:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(podcast_json(p, request), status=200)


@csrf_exempt
@require_http_methods(["POST"])
def podcast_create(request):
    obj = PodcastEpisode(
        title   = (request.POST.get("title") or "").strip(),
        host    = (request.POST.get("host") or "").strip(),
        genreid = (request.POST.get("genreid") or "").strip(),
        episode = _to_int_or_none(request.POST.get("episode")),
        info    = (request.POST.get("info") or "").strip(),
        adult   = (request.POST.get("adult") in ("true","1","on","yes")),
    )
    if request.FILES.get("audio_file"): obj.audio_file = request.FILES["audio_file"]
    if request.FILES.get("cover_image"): obj.cover_image = request.FILES["cover_image"]
    obj.duration_seconds = _to_int_or_none(request.POST.get("duration_seconds"))
    obj.save()
    return JsonResponse({"success": True, "podcast": podcast_json(obj, request)})


@csrf_exempt
@require_http_methods(["POST","PATCH","PUT"])
def podcast_update(request, pk: int):
    try:
        obj = PodcastEpisode.objects.get(pk=pk)
    except PodcastEpisode.DoesNotExist:
        return JsonResponse({"success": False, "error": "not found"}, status=404)

    for fld in ["title","host","genreid","info"]:
        if fld in request.POST:
            setattr(obj, fld, (request.POST.get(fld) or "").strip())
    if "episode" in request.POST:
        obj.episode = _to_int_or_none(request.POST.get("episode"))
    if "adult" in request.POST:
        obj.adult = (request.POST.get("adult") in ("true","1","on","yes"))
    if "duration_seconds" in request.POST:
        obj.duration_seconds = _to_int_or_none(request.POST.get("duration_seconds"))
    if request.FILES.get("audio_file"): obj.audio_file = request.FILES["audio_file"]
    if request.FILES.get("cover_image"): obj.cover_image = request.FILES["cover_image"]
    obj.save()
    return JsonResponse({"success": True, "podcast": podcast_json(obj, request)})


@csrf_exempt
@require_http_methods(["DELETE"])
def podcast_delete(request, pk: int):
    try:
        obj = PodcastEpisode.objects.get(pk=pk)
    except PodcastEpisode.DoesNotExist:
        return JsonResponse({"success": False, "error": "not found"}, status=404)
    obj.delete()
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def podcasts_bulk_delete(request):
    try:
        ids = json.loads(request.body.decode("utf-8")).get("ids", [])
    except Exception:
        ids = []
    qs = PodcastEpisode.objects.filter(pk__in=ids)
    deleted = qs.count()
    qs.delete()
    return JsonResponse({"success": True, "deleted": deleted})


# =========================
# Date range helpers
# =========================

def _date_range(request):
    tz = get_current_timezone()
    start_s = (request.GET.get('start') or '').strip()
    end_s   = (request.GET.get('end') or '').strip()
    start = end = None
    if start_s:
        d = parse_date(start_s)
        if d:
            start = make_aware(datetime.combine(d, time.min), tz)
    if end_s:
        d = parse_date(end_s)
        if d:
            end = make_aware(datetime.combine(d, time.max), tz)
    return start, end


def _apply_range(qs, created_field, start, end):
    try:
        field = qs.model._meta.get_field(created_field)
    except Exception:
        return qs
    if isinstance(field, (DateTimeField, DateField)):
        if start:
            qs = qs.filter(**{f"{created_field}__gte": start})
        if end:
            qs = qs.filter(**{f"{created_field}__lte": end})
    return qs


# =========================
# Dashboard
# =========================

def dashboard_summary(request):
    start, end = _date_range(request)

    tr_qs = _apply_range(Track.objects.all(), 'created_at', start, end)
    ab_qs = _apply_range(AudioBook.objects.all(), 'created_at', start, end)
    pc_qs = _apply_range(PodcastEpisode.objects.all(), 'created_at', start, end)

    us_all = User.objects.all()
    if hasattr(User, 'date_joined'):
        us_qs = _apply_range(us_all, 'date_joined', start, end)
    else:
        us_qs = us_all

    plays_tracks = Track.objects.aggregate(v=Coalesce(Sum(Cast('playsnum', IntegerField())), 0))['v'] or 0
    plays_ab     = AudioBook.objects.aggregate(v=Coalesce(Sum('playsnum'), 0))['v'] or 0
    plays_pc     = PodcastEpisode.objects.aggregate(v=Coalesce(Sum('playsnum'), 0))['v'] or 0

    def safe_size(qs, field_name):
        total = 0
        for o in qs.iterator():
            f = getattr(o, field_name, None)
            try:
                if f and getattr(f, 'path', None):
                    total += os.path.getsize(f.path)
            except Exception:
                pass
        return total

    storage_bytes = (
        safe_size(Track.objects.all(), 'audio') +
        safe_size(AudioBook.objects.all(), 'audio_file') +
        safe_size(PodcastEpisode.objects.all(), 'audio_file')
    )

    return JsonResponse({
        "success": True,
        "kpi": {
            "tracks_total": Track.objects.count(),
            "tracks_new": tr_qs.count(),
            "audiobooks_total": AudioBook.objects.count(),
            "audiobooks_new": ab_qs.count(),
            "podcasts_total": PodcastEpisode.objects.count(),
            "podcasts_new": pc_qs.count(),
            "plays_total": int(plays_tracks) + int(plays_ab) + int(plays_pc),
            "new_users": us_qs.count(),
            "storage_bytes": int(storage_bytes),
        }
    })


def dashboard_timeseries(request):
    start, end = _date_range(request)
    metric = (request.GET.get('metric') or 'uploads').lower()
    obj    = (request.GET.get('object') or 'track').lower()
    model  = Track if obj == 'track' else (AudioBook if obj == 'audiobook' else PodcastEpisode)

    if metric == 'uploads':
        qs = _apply_range(model.objects.all(), 'created_at', start, end)
        rows = (qs.annotate(d=TruncDate('created_at')).values('d').annotate(v=Count('id')).order_by('d'))
    else:
        if model is Track:
            qs = _apply_range(Track.objects.all(), 'created_at', start, end)
            rows = (qs.annotate(d=TruncDate('created_at'))
                      .values('d')
                      .annotate(v=Coalesce(Sum(Cast('playsnum', IntegerField())), 0))
                      .order_by('d'))
        else:
            qs = _apply_range(model.objects.all(), 'created_at', start, end)
            rows = (qs.annotate(d=TruncDate('created_at')).values('d').annotate(v=Coalesce(Sum('playsnum'), 0)).order_by('d'))

    data = [{"date": r["d"].isoformat(), "value": int(r["v"])} for r in rows]
    return JsonResponse({"success": True, "series": data})


def dashboard_top(request):
    start, end = _date_range(request)
    obj   = (request.GET.get('object') or 'track').lower()
    limit = max(int(request.GET.get('limit', 10)), 1)

    if obj == 'track':
        qs = _apply_range(Track.objects.all(), 'created_at', start, end)
        qs = qs.annotate(p=Cast('playsnum', IntegerField())).order_by('-p')[:limit]
        items = [{"id": t.id, "name": t.name, "artist": t.artistid,
                  "plays": int(t.p or 0), "time": fmt_time(int(t.time or 0))} for t in qs]
    elif obj == 'audiobook':
        qs = _apply_range(AudioBook.objects.all(), 'created_at', start, end).order_by('-playsnum')[:limit]
        items = [{"id": a.pk, "name": a.title, "author": a.author,
                  "plays": int(a.playsnum or 0), "time": fmt_time(a.duration_seconds)} for a in qs]
    else:
        qs = _apply_range(PodcastEpisode.objects.all(), 'created_at', start, end).order_by('-playsnum')[:limit]
        items = [{"id": p.pk, "name": p.title, "host": p.host,
                  "plays": int(p.playsnum or 0), "time": fmt_time(p.duration_seconds)} for p in qs]

    return JsonResponse({"success": True, "items": items})


def dashboard_recent(request):
    data = []
    for t in Track.objects.order_by('-created_at')[:10]:
        data.append({"type": "track", "id": t.id, "title": t.name, "at": t.created_at.isoformat()})
    for a in AudioBook.objects.order_by('-created_at')[:5]:
        data.append({"type": "audiobook", "id": a.pk, "title": a.title, "at": a.created_at.isoformat()})
    for p in PodcastEpisode.objects.order_by('-created_at')[:5]:
        data.append({"type": "podcast", "id": p.pk, "title": p.title, "at": p.created_at.isoformat()})
    data.sort(key=lambda x: x["at"], reverse=True)
    return JsonResponse({"success": True, "items": data[:20]})


def dashboard_moderation(request):
    missing_duration_tracks = Track.objects.filter(time__lte=0)
    missing_duration_ab = AudioBook.objects.filter(duration_seconds__isnull=True)
    missing_duration_pc = PodcastEpisode.objects.filter(duration_seconds__isnull=True)

    adult_count = (
        Track.objects.filter(adult=True).count() +
        AudioBook.objects.filter(adult=True).count() +
        PodcastEpisode.objects.filter(adult=True).count()
    )

    no_audio = (
        AudioBook.objects.filter(Q(audio_file__isnull=True) | Q(audio_file='')).count() +
        PodcastEpisode.objects.filter(Q(audio_file__isnull=True) | Q(audio_file='')).count()
    )

    return JsonResponse({
        "success": True,
        "queues": {
            "adult_flagged": adult_count,
            "missing_duration": {
                "tracks": missing_duration_tracks.count(),
                "audiobooks": missing_duration_ab.count(),
                "podcasts": missing_duration_pc.count(),
            },
            "missing_audio_count": no_audio,
        }
    })


# =========================
# Artists
# =========================

def _collect_counts(artist_ids):
    counts = {"tracks": {}, "audiobooks": {}, "podcasts": {}}

    if artist_ids:
        for row in (
            Track.objects
            .filter(artistid__in=artist_ids)
            .values("artistid")
            .annotate(c=Count("id"))
        ):
            counts["tracks"][row["artistid"]] = row["c"]

        for row in (
            AudioBook.objects
            .filter(author__in=artist_ids)
            .values("author")
            .annotate(c=Count("id"))
        ):
            counts["audiobooks"][row["author"]] = row["c"]

        for row in (
            PodcastEpisode.objects
            .filter(host__in=artist_ids)
            .values("host")
            .annotate(c=Count("id"))
        ):
            counts["podcasts"][row["host"]] = row["c"]

    return counts





@require_GET
def artistlinks_index(request):
    """
    Эндпоинт под фронт:
      GET /artistlinks          → ArtistLink[]
      GET /artistlinks?id=foo   → [ArtistLink]
    """
    id_param = (request.GET.get("id") or "").strip()
    qs = ArtistLinks.objects.all().order_by("name")
    if id_param:
        qs = qs.filter(pk=id_param)
    data = [artist_json(a, request) for a in qs]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def artist_create(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    raw_id = (request.POST.get("id") or "").strip()
    artist_id = raw_id or uuid.uuid4().hex[:12]
    if ArtistLinks.objects.filter(pk=artist_id).exists():
        return JsonResponse({"error": "id already exists"}, status=400)

    description = (request.POST.get("description") or "").strip()
    listeners = (request.POST.get("listeners") or request.POST.get("listener") or "0").strip()
    photo_file = request.FILES.get("photo")

    a = ArtistLinks(id=artist_id, name=name, description=description)
    if hasattr(a, "listeners"):
        setattr(a, "listeners", listeners)
    else:
        setattr(a, "listener", listeners)
    if photo_file:
        a.photo = photo_file
    a.save()

    return JsonResponse({"ok": True, "item": artist_json(a, request)})


@require_http_methods(["GET"])
def artist_detail(request, artist_id):
    try:
        a = ArtistLinks.objects.get(pk=artist_id)
    except ArtistLinks.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse(artist_json(a, request), status=200)


@csrf_exempt
@require_http_methods(["POST", "PUT", "PATCH"])
def artist_update(request, artist_id):
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = {}
        name         = payload.get("name")
        description  = payload.get("description")
        new_id       = (payload.get("new_id") or "").strip()
        listeners_in = payload.get("listeners") if payload.get("listeners") is not None else payload.get("listener")
        photo_file   = None
    else:
        name         = request.POST.get("name")
        description  = request.POST.get("description")
        new_id       = (request.POST.get("new_id") or "").strip()
        listeners_in = (request.POST.get("listeners") or request.POST.get("listener"))
        photo_file   = request.FILES.get("photo")

    try:
        old = ArtistLinks.objects.get(pk=artist_id)
    except ArtistLinks.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    try:
        with transaction.atomic():
            if new_id and new_id != artist_id:
                if ArtistLinks.objects.filter(pk=new_id).exists():
                    return JsonResponse({"error": "id already exists"}, status=400)

                new = ArtistLinks(
                    id=new_id,
                    name=(name.strip() if isinstance(name, str) else old.name),
                    description=((description or "").strip() if description is not None else (old.description or "")),
                )
                old_ls = (getattr(old, "listeners", None) or getattr(old, "listener", None) or "0")
                set_ls = (listeners_in.strip() if isinstance(listeners_in, str) else old_ls)
                if hasattr(new, "listeners"):
                    setattr(new, "listeners", set_ls)
                else:
                    setattr(new, "listener", set_ls)

                new.photo = photo_file if photo_file else old.photo
                new.save()

                try:
                    Track.objects.filter(artist=old).update(artist=new)
                except Exception:
                    pass
                Track.objects.filter(artistid__iexact=artist_id).update(artistid=new_id)
                try:
                    AudioBook.objects.filter(author_fk=old).update(author_fk=new)
                except Exception:
                    pass
                AudioBook.objects.filter(author__iexact=artist_id).update(author=new_id)
                try:
                    PodcastEpisode.objects.filter(host_fk=old).update(host_fk=new)
                except Exception:
                    pass
                PodcastEpisode.objects.filter(host__iexact=artist_id).update(host=new_id)

                old.delete()
                return JsonResponse({"ok": True, "item": artist_json(new, request)})

            # обычное обновление
            if name is not None:
                old.name = name.strip()
            if description is not None:
                old.description = (description or "").strip()
            if isinstance(listeners_in, str):
                if hasattr(old, "listeners"):
                    setattr(old, "listeners", listeners_in.strip())
                else:
                    setattr(old, "listener", listeners_in.strip())
            if photo_file:
                old.photo = photo_file
            old.save()

            return JsonResponse({"ok": True, "item": artist_json(old, request)})

    except IntegrityError as e:
        return JsonResponse({"error": f"DB integrity error: {e}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def artist_delete(request, artist_id):
    try:
        a = ArtistLinks.objects.get(pk=artist_id)
    except ArtistLinks.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    a.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def artists_bulk_delete(request):
    ids = []
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
            ids = payload.get("ids", [])
        except Exception:
            ids = []
    else:
        ids = request.POST.getlist("ids")
        if not ids and request.POST.get("ids"):
            ids = [x.strip() for x in request.POST["ids"].split(",") if x.strip()]

    if not ids:
        return JsonResponse({"error": "ids required"}, status=400)

    qs = ArtistLinks.objects.filter(pk__in=ids)
    deleted = qs.count()
    qs.delete()
    return JsonResponse({"ok": True, "deleted": deleted})
@require_http_methods(["GET"])
def artists_list(request):
    """Админский листинг с пагинацией (оставляем как было)."""
    search = (request.GET.get("search") or "").strip()
    qs = ArtistLinks.objects.all().order_by("name")
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(id__icontains=search)
        )

    # БЫЛО: paged = _paginate(qs, request, default_page_size=10)
    paged = _paginate_qs(qs, request, default_page_size=10)  # ← так правильно

    data = [artist_json(a, request) for a in paged["items"]]
    return JsonResponse({
        "items": data,
        "page": paged["page"],
        "pages": paged["total_pages"],
        "total": paged["total"],
        "page_size": paged["page_size"],
        "has_next": paged["page"] < paged["total_pages"],
        "has_prev": paged["page"] > 1,
    })
def _paginate_qs(qs, request, default_size: int = 20, **kwargs):
    """
    Унифицированная пагинация.
    Понимает оба алиаса:
      - default_size (новое имя)
      - default_page_size (старое имя, чтобы не падали старые вызовы)
    Параметры запроса:
      ?page, ?page_size (или ?size)
    """
    # поддержка старого имени аргумента
    if "default_page_size" in kwargs and isinstance(kwargs["default_page_size"], int):
        default_size = kwargs["default_page_size"]

    # читаем page/page_size
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except Exception:
        page = 1

    raw_ps = request.GET.get("page_size") or request.GET.get("size") or default_size
    try:
        page_size = max(int(raw_ps), 1)
    except Exception:
        page_size = default_size

    total = qs.count()
    start, end = (page - 1) * page_size, page * page_size
    items = list(qs[start:end])
    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
@require_GET
def albums_table(request):
    """
    Таблица альбомов по трекам: DISTINCT albumid + count(tracks).
    Параметры:
      q – поиск по albumid (icontains)
      page, page_size – пагинация
    """
    q = (request.GET.get("q") or "").strip()
    base = Track.objects.exclude(albumid__isnull=True).exclude(albumid="")

    if q:
        base = base.filter(albumid__icontains=q)

    agg = (base.values("albumid")
                .annotate(count=Count("id"))
                .order_by("-count", "albumid"))

    paged = _paginate_qs(agg, request, default_page_size=20)
    items = [{"albumid": row["albumid"], "tracks_count": row["count"]} for row in paged["items"]]

    return JsonResponse({
        "success": True,
        "items": items,
        "page": paged["page"],
        "page_size": paged["page_size"],
        "total": paged["total"],
        "total_pages": paged["total_pages"],
    })


@require_GET
def genres_table(request):
    """
    Таблица жанров по трекам: DISTINCT genreid + count(tracks).
    Параметры:
      q – поиск по genreid (icontains)
      page, page_size – пагинация
    """
    q = (request.GET.get("q") or "").strip()
    base = Track.objects.exclude(genreid__isnull=True).exclude(genreid="")

    if q:
        base = base.filter(genreid__icontains=q)

    agg = (base.values("genreid")
                .annotate(count=Count("id"))
                .order_by("-count", "genreid"))

    paged = _paginate_qs(agg, request, default_page_size=20)
    items = [{"genreid": row["genreid"], "tracks_count": row["count"]} for row in paged["items"]]

    return JsonResponse({
        "success": True,
        "items": items,
        "page": paged["page"],
        "page_size": paged["page_size"],
        "total": paged["total"],
        "total_pages": paged["total_pages"],
    })


@require_http_methods(["GET"])
def artist_content(request, artist_id: str):
    """Контент по артисту: треки, аудиокниги, подкасты (с поддержкой строковых ID и FK)."""
    try:
        artist = ArtistLinks.objects.get(pk=artist_id)
    except ArtistLinks.DoesNotExist:
        artist = None

    # Tracks
    tr_qs = Track.objects.all()
    tr_qs = tr_qs.filter(Q(artist=artist) | Q(artistid__iexact=artist_id)) if artist else tr_qs.filter(artistid__iexact=artist_id)

    # Audiobooks
    ab_qs = AudioBook.objects.all()
    ab_qs = ab_qs.filter(Q(author_fk=artist) | Q(author__iexact=artist_id)) if artist else ab_qs.filter(author__iexact=artist_id)

    # Podcasts
    pc_qs = PodcastEpisode.objects.all()
    pc_qs = pc_qs.filter(Q(host_fk=artist) | Q(host__iexact=artist_id)) if artist else pc_qs.filter(host__iexact=artist_id)

    try:
        limit = max(1, int(request.GET.get("limit", 20)))
    except Exception:
        limit = 20

    tr_qs = tr_qs.order_by('-created_at' if hasattr(Track, 'created_at') else '-id')[:limit]
    ab_qs = (ab_qs.order_by('-created_at') if hasattr(AudioBook, 'created_at') else ab_qs.order_by('-id'))[:limit]
    pc_qs = (pc_qs.order_by('-created_at') if hasattr(PodcastEpisode, 'created_at') else pc_qs.order_by('-id'))[:limit]

    tracks = [track_json(t, request) for t in tr_qs]
    audiobooks = [audiobook_json(x, request) for x in ab_qs]
    podcasts   = [podcast_json(x, request) for x in pc_qs]

    artist_payload = (artist_json(artist, request) if artist else {
        'id': artist_id, 'name': artist_id, 'description': '', 'photo': '', 'listeners': '0'
    })

    return JsonResponse({
        'success': True,
        'artist': artist_payload,
        'counts': {
            'tracks': Track.objects.filter(Q(artist=artist) | Q(artistid__iexact=artist_id)).count() if artist
                      else Track.objects.filter(artistid__iexact=artist_id).count(),
            'audiobooks': AudioBook.objects.filter(Q(author_fk=artist) | Q(author__iexact=artist_id)).count() if artist
                          else AudioBook.objects.filter(author__iexact=artist_id).count(),
            'podcasts': PodcastEpisode.objects.filter(Q(host_fk=artist) | Q(host__iexact=artist_id)).count() if artist
                        else PodcastEpisode.objects.filter(host__iexact=artist_id).count(),
        },
        'tracks': tracks,
        'audiobooks': audiobooks,
        'podcasts': podcasts,
        'limit': limit
    })


# =========================
# Bulk ops for tracks
# =========================

@csrf_exempt
@require_http_methods(["POST"])
def bulk_delete_tracks(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        ids = data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return JsonResponse({'success': False, 'error': 'ids must be non-empty list'}, status=400)

        deleted = Track.objects.filter(id__in=ids).delete()[0]
        return JsonResponse({'success': True, 'deleted': deleted})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _shadow_track_id(kind: str, src_id) -> str:
    return f"__{kind}_{src_id}"


def _ensure_shadow_track_from_ab(ab: AudioBook) -> Track:
    tid = _shadow_track_id("ab", ab.pk)
    t, created = Track.objects.get_or_create(
        id=tid,
        defaults={
            "name": ab.title or "",
            "artistid": ab.author or "",
            "albumid": "",
            "genreid": ab.genreid or "",
            "playsnum": "0",
            "adult": bool(ab.adult),
            "time": int(ab.duration_seconds or 0),
        },
    )
    # синхронизируем поля при каждом вызове
    t.name = ab.title or ""
    t.artistid = ab.author or ""
    t.genreid = ab.genreid or ""
    t.adult = bool(ab.adult)
    t.time = int(ab.duration_seconds or 0)

    # Подцепляем те же файлы (без копирования)
    if ab.audio_file and getattr(ab.audio_file, "name", ""):
        t.audio.name = ab.audio_file.name
    if ab.cover_image and getattr(ab.cover_image, "name", ""):
        t.cover.name = ab.cover_image.name
    t.save()
    return t


def _ensure_shadow_track_from_pc(pc: PodcastEpisode) -> Track:
    tid = _shadow_track_id("pc", pc.pk)
    t, created = Track.objects.get_or_create(
        id=tid,
        defaults={
            "name": pc.title or "",
            "artistid": pc.host or "",
            "albumid": "",
            "genreid": pc.genreid or "",
            "playsnum": "0",
            "adult": bool(pc.adult),
            "time": int(pc.duration_seconds or 0),
        },
    )
    t.name = pc.title or ""
    t.artistid = pc.host or ""
    t.genreid = pc.genreid or ""
    t.adult = bool(pc.adult)
    t.time = int(pc.duration_seconds or 0)

    if pc.audio_file and getattr(pc.audio_file, "name", ""):
        t.audio.name = pc.audio_file.name
    if pc.cover_image and getattr(pc.cover_image, "name", ""):
        t.cover.name = pc.cover_image.name
    t.save()
    return t
# helpers для shadow-треков автора
def _ensure_shadow_track_from_ar(ar: ArtistLinks) -> Track:
    """
    Делаем стабильный Track с PK вида "__ar_<artist_id>".
    Без аудио, time=0 — он нужен только как «идентификатор» в PlaylistItem.
    """
    sid = f"__ar_{str(ar.pk).strip()}"
    t = Track.objects.filter(pk=sid).first()
    if t:
        # актуализируем название/артиста на всякий случай
        changed = False
        if t.name != (ar.name or ""):
            t.name = ar.name or ""
            changed = True
        if t.artistid != str(ar.pk):
            t.artistid = str(ar.pk)
            changed = True
        if changed:
            t.save(update_fields=["name", "artistid"])
        return t

    return Track.objects.create(
        id=sid,
        name=ar.name or str(ar.pk),
        artistid=str(ar.pk),
        albumid=None,
        genreid=None,
        playsnum='0',
        adult=False,
        time=0,          # важно: не ломаем фронт — нет «плеера»
    )



def _resolve_to_track_ids(raw_ids: list[str]) -> list[str]:
    """
    Принимает список id из фронта (могут быть TR/AB/PC).
    Возвращает список id ТРЕКОВ (включая созданные зеркала).
    """
    out: list[str] = []
    for rid in raw_ids:
        rid = str(rid).strip()
        if not rid:
            continue
        # уже трек?
        if Track.objects.filter(pk=rid).exists():
            out.append(rid)
            continue
        # аудиокнига?
        ab = AudioBook.objects.filter(pk=rid).first()
        if ab:
            t = _ensure_shadow_track_from_ab(ab)
            out.append(t.pk)
            continue
        # подкаст?
        pc = PodcastEpisode.objects.filter(pk=rid).first()
        if pc:
            t = _ensure_shadow_track_from_pc(pc)
            out.append(t.pk)
            continue
        # иначе пропускаем
    # уникальность + порядок
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq
from django.views.decorators.http import require_GET

@require_GET
def audiobook_detail_simple(request, pk: int):
    a = AudioBook.objects.filter(pk=pk).first()
    if not a:
        return JsonResponse({"detail": "Not found"}, status=404)
    return JsonResponse(audiobook_json(a, request), status=200)
