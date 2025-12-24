# urls.py
from django.conf import settings 
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

urlpatterns = [
    path('', auth_views.LoginView.as_view(
    template_name='custom_admin/login.html'
    ), name='login'),
      path('dashboard/', login_required(
        TemplateView.as_view(template_name='custom_admin/dashboard.html')  # или твой шаблон
    ), name='dashboard'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('api/', include('lumituneapp.urls')),

    # (опционально) защищённая страница после входа
    path('dashboard/', login_required(
        TemplateView.as_view(template_name='custom admin/dashboard.html')
    ), name='dashboard'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)