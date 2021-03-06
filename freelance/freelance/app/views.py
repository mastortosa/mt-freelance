# -*- coding: utf-8 -*-

import json
from datetime import datetime, timedelta

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import timezone
from django.views import generic

from freelance.app.models import Invoice, Client, Day, Settings
from freelance.app import utils


class LoginRequiredMixin(object):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return redirect('login')
        return super(LoginRequiredMixin, self).dispatch(
            request, *args, **kwargs)


class JsonMixin(object):

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(JsonMixin, self).dispatch(
                request, *args, **kwargs)
        except ValidationError as e:
            return HttpResponse(
                json.dumps({'errors': self._format_errors(e.message_dict)}),
                content_type='application/json',
                status=400)

    def _respond(self, data=None, status=200, fields=[]):
        if data is not None and not isinstance(data, str):
            data = utils.serialize(data, fields)
        return HttpResponse(data,
                            status=status,
                            content_type='application/json')

    def _format_errors(self, error_dict):
        return [{'field': k, 'errors': v} for k, v in error_dict.items()]


class HomeView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        ctx = super(HomeView, self).get_context_data(**kwargs)
        invoices = Invoice.objects.all()

        ctx['last_edited_invoices'] = []
        t0 = timezone.now() - timedelta(days=90)
        for invoice in invoices.filter(updated__gte=t0):
            invoice = utils.serialize_invoice(
                invoice, self.request.user.settings, False)
            ctx['last_edited_invoices'].append(invoice)

        def extended_invoice(invoice_queryset):
            return [utils.serialize_invoice(
                    i, self.request.user.settings, False)
                    for i in invoice_queryset.all()]

        ctx['draft_invoices'] = extended_invoice(invoices.filter(status=0))
        ctx['saved_invoices'] = extended_invoice(invoices.filter(status=1))

        def money_status(query):
            x = sum(i.total for i in invoices.filter(**query))
            return self.request.user.settings.format_money(x)

        ctx['money_status'] = {
            'paid': money_status({'status': 3}),
            'unpaid': money_status({'status': 2}),
            'unsent': money_status({'status__lt': 2})
        }
        return ctx


class ClientListView(LoginRequiredMixin, generic.ListView):
    model = Client
    template_name = 'client_list.html'


class ClientView(LoginRequiredMixin, generic.UpdateView):
    model = Client
    template_name = 'client.html'

    def get(self, request, *args, **kwargs):
        if 'delete' in request.GET:
            return self.delete(request, *args, **kwargs)
        return super(ClientView, self).get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.get_object().delete()
        return HttpResponseRedirect(reverse('clients'))

    def get_object(self):
        if 'pk' in self.kwargs:
            return super(ClientView, self).get_object()

    def get_success_url(self):
        return reverse('client', args=[self.object.pk])


class CalendarView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'calendar.html'


class DayListJsonView(LoginRequiredMixin, JsonMixin, generic.View):

    def get(self, request, *args, **kwargs):
        return self._respond(Day.objects.all(),
                             fields=['date', 'half', 'invoice'])

    def post(self, request, *args, **kwargs):
        day_list = []
        for day in json.loads(request.body):
            obj, _ = Day.objects.get_or_create(date=day['date'])
            if not obj.invoice:
                obj.half = day.get('half', False)
                obj.save()
                day_list.append(day)
        return self._respond(day_list)

    def delete(self, request, *args, **kwargs):
        for day in json.loads(request.body):
            try:
                obj = Day.objects.get(date=day['date'], invoice=None)
            except Day.DoesNotExist:
                continue
            else:
                obj.delete()
        return self._respond(status=204)


class InvoiceListView(LoginRequiredMixin, generic.ListView):
    model = Invoice
    template_name = 'invoice_list.html'

    def get_context_data(self, **kwargs):
        ctx = super(InvoiceListView, self).get_context_data(**kwargs)
        object_list = []
        for invoice in ctx['object_list']:
            invoice = utils.serialize_invoice(
                invoice, self.request.user.settings, as_json=False)
            object_list.append(invoice)
        ctx['object_list'] = object_list
        return ctx


class InvoiceView(LoginRequiredMixin, generic.DetailView):
    template_name = 'invoice.html'

    def get(self, request, *args, **kwargs):
        if 'delete' in request.GET:
            return self.delete(request, *args, **kwargs)

        self.object = self.get_object()

        if not self.object:
            return HttpResponseRedirect(reverse('calendar'))

        if 'number' not in kwargs:
            return HttpResponseRedirect(
                reverse('invoice', args=[self.object.number]))

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def delete(self, request, *args, **kwargs):
        self.get_object().delete()
        return HttpResponseRedirect(reverse('invoices'))

    def get_object(self):
        """
        /invoice/20150103
            get invoice from number
        /invoice
            try to create an invoice from days, return None otherwise
        /invoice?from=file
            force to creat an invoice from file
        """
        if 'number' in self.kwargs:
            return self._get_object_from_number(self.kwargs['number'])

        if self.request.GET.get('from', None) == 'file':
            return self._get_new_object()

        days = Day.objects.filter(invoice=None)
        if days:
            return self._get_object_from_days(days)

    def get_context_data(self, **kwargs):
        ctx = super(InvoiceView, self).get_context_data(**kwargs)
        ctx['object'] = utils.serialize_invoice(
            self.object, self.request.user.settings, as_json=False)
        ctx['object_json'] = utils.serialize(ctx['object'])
        ctx['clients'] = Client.objects.all()
        return ctx

    def _get_object_from_number(self, number):
        return Invoice.objects.get(number=number)

    def _get_object_from_days(self, days):
        """Get a new invoice created from active days."""
        invoice = Invoice.objects.create(
            daily_rate=self.request.user.settings.default_daily_rate,
            tax=self.request.user.settings.default_tax)
        for i in days:
            i.invoice = invoice
            i.save()
        invoice.save(usettings=self.request.user.settings)  # Set subtotal.
        return invoice

    def _get_new_object(self):
        return Invoice.objects.create(
            daily_rate=self.request.user.settings.default_daily_rate,
            tax=self.request.user.settings.default_tax,
            created_from=1)


class InvoiceJsonView(JsonMixin, LoginRequiredMixin, generic.View):

    def _invoice_response(self, invoice):
        return self._respond(
            utils.serialize_invoice(invoice, self.request.user.settings))

    def post(self, request, *args, **kwargs):
        """Method used just for upload a pdf file by request.FILES"""
        invoice = self.get_object()
        pdf = request.FILES.get('pdf', None)
        if pdf:
            invoice.save_pdf(pdf)
            return self._invoice_response(invoice)
        else:
            return self._respond(status=400)

    def put(self, request, *args, **kwargs):
        invoice = self.get_object()
        if 'save' in request.GET:
            invoice.status = 1
            invoice.full_clean()  # Validate blank fields, not the best way.
        elif 'email' in request.GET:
            password = json.loads(request.body)['password']
            try:
                utils.email_invoice(invoice, request.user.settings, password)
            except:
                return self._respond('Error sending email', stauts=500)
            else:
                invoice.status = 2
        else:
            for k, v in json.loads(request.body).items():
                if k == 'client':
                    v = Client.objects.get(pk=v)
                elif k.startswith('date'):
                    # Convert before saving to keep date as a DateTime object.
                    try:
                        # User date format.
                        v = datetime.strptime(
                            v, request.user.settings.date_format)
                    except ValueError:
                        # ISO date format.
                        v = datetime.strptime(v, '%Y-%m-%d')
                setattr(invoice, k, v)
        invoice.save(usettings=request.user.settings)
        return self._invoice_response(invoice)

    def delete(self, request, *args, **kwargs):
        invoice = self.get_object()
        invoice.delete()
        return self._respond(status=204)

    def get_object(self):
        return Invoice.objects.get(pk=self.kwargs['pk'])


class SettingsView(LoginRequiredMixin, generic.UpdateView):
    model = Settings
    template_name = 'settings.html'

    def get_object(self, queryset=None):
        return self.request.user.settings

    def get_success_url(self):
        return reverse('settings')


class LoginView(generic.TemplateView):
    template_name = 'login.html'

    def post(self, request):
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        return redirect('login')


class LogoutView(LoginRequiredMixin, generic.View):

    def get(self, request):
        logout(request)
        return redirect('login')
