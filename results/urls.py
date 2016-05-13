from django.conf.urls import url, include

from . import views

app_name = 'results'
urlpatterns = [
    url(r'^', include('django.contrib.auth.urls')),
    url(r'^$', views.index, name='index'),
    url(r'^provinces$', views.provinces, name='provinces'),
    url(r'^types$', views.types, name='types'),
    url(r'^sizes$', views.sizes, name='sizes'),
    url(r'^map$', views.map, name='map'),
    url(r'^global$', views.global_stats, name='global'),
    url(r'^query$', views.query, name='query'),
    url(r'^edit$', views.edit_results, name='edit'),
]