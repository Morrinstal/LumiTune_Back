from django.contrib.auth.views import LogoutView
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Auth/Admin
    path('auth/', views.admin_login_view, name='admin_login'),
    path('register/', views.register_view, name='admin_register'),
    path('password_reset/', views.AdminPasswordResetView.as_view(), name='password_reset_email'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/summary/', views.dashboard_summary),
    path('dashboard/timeseries/', views.dashboard_timeseries),
    path('dashboard/top/', views.dashboard_top),
    path('dashboard/recent/', views.dashboard_recent),
    path('dashboard/moderation/', views.dashboard_moderation),
    path('logout/', LogoutView.as_view(next_page='admin_login'), name='logout'),

    # Tracks
    path('tracks/', views.get_tracks, name='tracks_index'),
    path('get_tracks/', views.get_tracks, name='get_tracks'),
    path('tracks/<str:track_id>/', views.track_detail_simple, name='track_detail'),
    path('create_track/', views.create_track, name='create_track'),
    path('update_track/<str:track_id>/', views.update_track, name='update_track'),
    path('delete_track/<str:track_id>/', views.delete_track, name='delete_track'),
    path('bulk_delete_tracks/', views.bulk_delete_tracks, name='bulk_delete_tracks'),
    path('stream_track/<str:track_id>/', views.stream_track, name='stream_track'),
    path('tracks/by/<str:field>/', views.tracks_by_field, name='tracks_by_field'),
    path('tracks/by/<str:field>/<path:value>/', views.tracks_by_field, name='tracks_by_field_value'),

    path('auth/jwt/create/',  TokenObtainPairView.as_view(), name='jwt_create'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(),    name='jwt_refresh'),

    # публичная регистрация и профиль
    path('auth/register/', views.RegisterAPIView.as_view(), name='public_register'),
    path('auth/me/',       views.MeAPIView.as_view(),       name='me'),
    path('auth/password/reset/', views.PasswordResetCodeRequestAPIView.as_view(), name='password_reset_code_request'),
    path('auth/password/reset/verify/', views.PasswordResetCodeVerifyAPIView.as_view(), name='password_reset_code_verify'),
    path('auth/password/reset/confirm/', views.PasswordResetCodeConfirmAPIView.as_view(), name='password_reset_code_confirm'),

    # Customers
    path('customers/', views.get_customers_api, name='get_customers'),
    path('customers/create/', views.create_customer, name='create_customer'),
    path('customers/update/<int:user_id>/', views.update_customer, name='update_customer'),
    path('customers/delete/<int:user_id>/', views.delete_customer, name='delete_customer'),
    path('customers/bulk_delete/', views.bulk_delete_customers, name='bulk_delete_customers'),

    # Playlists
    path('playlists/', views.playlists_index, name='playlists_index'),
    path('playlists',  views.playlists_index, name='playlists_index_noslash'),

    # 2) Доп. утилитарные ручки
    path('playlists/create/',             views.create_playlist,  name='create_playlist'),
    path('playlists/update/<int:pl_id>/', views.update_playlist,  name='playlists_update'),
    path('playlists/update/<str:pl_id>/', views.update_playlist,  name='playlists_update_str'),
    path('playlists/delete/<int:pl_id>/', views.delete_playlist,  name='playlists_delete'),
    path('playlists/delete/<str:pl_id>/', views.delete_playlist,  name='playlists_delete_str'),

    # 3) Деталька
    path('playlists/<str:pl_id>/', views.playlist_detail, name='playlist_detail'),

    # 4) Элементы плейлиста
    path('playlistitems',                 views.playlist_items, name='playlist_items_noslash'),
    path('playlistitems/',                views.playlist_items, name='playlist_items'),
    path('playlistItems/',                views.playlist_items, name='playlist_items_camel'),
    path('playlists/<str:pl_id>/items/',  views.playlist_items, name='playlist_items_rest'),
    path('playlists/<str:pl_id>/tracks/', views.playlist_items, name='playlist_tracks_alias'),

    # Audiobooks
    path('audiobooks/', views.audiobooks_list, name='audiobooks_list'),
    path('audiobooks/create/', views.audiobook_create, name='audiobook_create'),
    path('audiobooks/update/<int:pk>/', views.audiobook_update, name='audiobook_update'),
    path('audiobooks/delete/<int:pk>/', views.audiobook_delete, name='audiobook_delete'),
    path('audiobooks/bulk_delete/', views.audiobooks_bulk_delete, name='audiobooks_bulk_delete'),
    path('audiobooks/<int:pk>/', views.audiobook_detail_simple, name='audiobook_detail'),

    # Podcasts
    path('podcasts/', views.podcasts_list, name='podcasts_list'),
    path('podcasts/<int:pk>/', views.podcastepisode_detail_simple, name='podcast_detail'),
    path('podcasts/create/', views.podcast_create, name='podcast_create'),
    path('podcasts/update/<int:pk>/', views.podcast_update, name='podcast_update'),
    path('podcasts/delete/<int:pk>/', views.podcast_delete, name='podcast_delete'),
    path('podcasts/bulk_delete/', views.podcasts_bulk_delete, name='podcasts_bulk_delete'),
    path('podcastepisodes/', views.podcasts_list, name='podcastepisodes_list'),
    path('podcastepisodes/<int:pk>/', views.podcastepisode_detail_simple, name='podcastepisode_detail'),

    # Artists (админские CRUD) + контент
    path('artists/', views.artists_list, name='artists_list'),
    path('artists/create/', views.artist_create, name='artist_create'),
    path('artists/bulk_delete/', views.artists_bulk_delete, name='artists_bulk_delete'),
    path('artists/<str:artist_id>/', views.artist_detail, name='artist_detail'),
    path('artists/<str:artist_id>/update/', views.artist_update, name='artist_update'),
    path('artists/<str:artist_id>/delete/', views.artist_delete, name='artist_delete'),
    path('artists/<str:artist_id>/content/', views.artist_content, name='artist_content'),

    # ArtistLinks (фронтовый индекс)
    path('artistlinks/', views.artistlinks_index, name='artistlinks_index'),

    # ===== ТАБЛИЦЫ НА ОСНОВЕ TRACKS (альбомы/жанры) =====
    path('albums/', views.albums_table, name='albums_table'),
    path('genres/', views.genres_table, name='genres_table'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
