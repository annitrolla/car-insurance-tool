from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'^results$', views.result_server, name="result_server"),
    url(r'^recognize_car_plate/?', views.recognize_car_plate),
]
