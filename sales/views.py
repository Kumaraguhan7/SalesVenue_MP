from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Ad
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import AdForm, AdImageFormSet

class AdListView(ListView):
    model = Ad
    template_name = 'ad_list_view.html'
    context_object_name = 'ads'
    
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # If not authenticated, render a different template with a welcome message
            return render(request, 'welcome.html')

        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Ad.objects.filter(is_active=True).select_related('user', 'category') \
                                                .prefetch_related('images') \
                                                .order_by('-created_at')

class AdDetailView(LoginRequiredMixin ,DetailView):
    model = Ad
    template_name = 'ad_detail_view.html'
    context_object_name = 'ad'

    def get_queryset(self):
        return Ad.objects.filter(is_active=True).select_related('user').prefetch_related('images')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ad = self.object
        user = self.request.user
        context['show_contact_info'] = ad.is_visible_to_user(user)
        
        ad_owner = ad.user
        context['show_user_contact_info'] = ad_owner.contact_info_visibility
        context['user_phone_number'] = ad_owner.phone_number if ad_owner.contact_info_visibility else None
        context['images'] = ad.images.all()

        return context

class AdCreateView(LoginRequiredMixin, CreateView):
    model = Ad
    template_name = 'ad_form.html'
    form_class = AdForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['images_formset'] = AdImageFormSet(self.request.POST, self.request.FILES)
        else:
            context['images_formset'] = AdImageFormSet()
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        context = self.get_context_data()
        images_formset = context['images_formset']
        if images_formset.is_valid():
            self.object = form.save()
            images_formset.instance = self.object
            images_formset.save()
            messages.success(self.request, "Ad created successfully!")
            return redirect(self.object.get_absolute_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


class AdUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Ad
    template_name = 'ad_form.html'
    form_class = AdForm

    def test_func(self):
        return self.request.user == self.get_object().user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['images_formset'] = AdImageFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['images_formset'] = AdImageFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        images_formset = context['images_formset']
        if images_formset.is_valid():
            self.object = form.save()
            images_formset.instance = self.object
            images_formset.save()
            messages.success(self.request, "Ad updated successfully!")
            return redirect(self.object.get_absolute_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))


class AdDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Ad
    template_name = 'ad_confirm_delete.html'
    success_url = reverse_lazy('ad_list')

    def test_func(self):
        ad = self.get_object()
        return self.request.user == ad.user
