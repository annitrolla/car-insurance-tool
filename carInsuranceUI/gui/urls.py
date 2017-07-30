from django.conf.urls import url
from . import views
from carInsuranceUI import settings
from django.views.static import serve

urlpatterns = [
    url(r'^$', views.index),
    url(r'^recognize_car_plate/?', views.recognize_car_plate),
    url(r'^image_files/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]
