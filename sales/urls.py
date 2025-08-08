from django.urls import path
from .views import AdListView, AdDetailView, AdCreateView, AdUpdateView, AdDeleteView

urlpatterns = [
    path('', AdListView.as_view(), name='ad_list'),
    path('ads/<int:pk>/', AdDetailView.as_view(), name='ad_detail'),
    path('ad/new/', AdCreateView.as_view(), name='ad_create'),
    path('ad/<int:pk>/update/', AdUpdateView.as_view(), name='ad_update'),
    path('ad/<int:pk>/delete/', AdDeleteView.as_view(), name='ad_delete'),
]