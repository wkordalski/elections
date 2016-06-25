from django.conf.urls import url, include

from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r'provinces', views.ProviceViewSet)
router.register(r'municipalities', views.MunicipalityViewSet)
router.register(r'candidates', views.CandidateViewSet)
router.register(r'results', views.ElectionResultsViewSet)
router.register(r'query', views.MunicipalityQueryView, base_name='query')

app_name = 'results'
urlpatterns = [
    url(r'^', include('django.contrib.auth.urls')),
    url(r'^$', views.index, name='index'),
    url(r'^global$', views.global_stats, name='global'),
    url(r'^edit$', views.edit_results, name='edit'),
    url(r'^api/', include(router.urls)),
    url(r'^api/sizes/', views.MunicipalitySizesView.as_view(), name='municipality-sizes'),
    url(r'^api/types/', views.MunicipalityTypesView.as_view(), name='municipality-types'),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]