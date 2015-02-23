from django.conf.urls import patterns, include, url
from django.conf import settings

from freelance.app import views


urlpatterns = patterns('',

    url(r'^$',
        views.HomeView.as_view(),
        name='home'),

    url(r'^login$',
        views.LoginView.as_view(),
        name='login'),

    url(r'^logout$',
        views.LogoutView.as_view(),
        name='logout'),

    url(r'^invoices$',
        views.InvoiceListView.as_view(),
        name='invoices'),

    url(r'^invoices/new$',
        views.InvoiceView.as_view(),
        name='invoice_new'),

    url(r'^invoices/(?P<number>.*)$',
        views.InvoiceView.as_view(),
        name='invoice'),

    url(r'^clients$',
        views.ClientListView.as_view(),
        name='clients'),

    url(r'^clients/new$',
        views.ClientView.as_view(),
        name='client_new'),

    url(r'^clients/(?P<pk>\d+)$',
        views.ClientView.as_view(),
        name='client'),

    url(r'^calendar$',
        views.CalendarView.as_view(),
        name='calendar'),

    url(r'^api/day$',
        views.DayJsonView.as_view(),
        name='api_day'),

    url(r'^api/days$',
        views.DayListJsonView.as_view(),
        name='api_days'),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', 'django.views.static.serve', {
        'document_root': settings.MEDIA_ROOT}))
