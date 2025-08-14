from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Ad, Conversation, Message
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import AdForm, AdImageFormSet, MessageForm
from .mixins import AdOwnerRequiredMixin
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Case, When, F
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

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

class AdImageFormsetMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['images_formset'] = AdImageFormSet(
                self.request.POST, self.request.FILES, instance=getattr(self, 'object', None)
            )
        else:
            context['images_formset'] = AdImageFormSet(instance=getattr(self, 'object', None))
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        images_formset = context['images_formset']
        if images_formset.is_valid():
            self.object = form.save()
            images_formset.instance = self.object
            images_formset.save()
            messages.success(self.request, self.success_message)
            return redirect(self.object.get_absolute_url())
        return self.render_to_response(self.get_context_data(form=form))

class AdCreateView(LoginRequiredMixin, AdImageFormsetMixin, CreateView):
    model = Ad
    template_name = 'ad_form.html'
    form_class = AdForm
    success_message = "Ad created successfully!"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class AdUpdateView(LoginRequiredMixin, AdOwnerRequiredMixin, AdImageFormsetMixin, UpdateView):
    model = Ad
    template_name = 'ad_form.html'
    form_class = AdForm
    pk_url_kwarg = 'ad_id'
    success_message = "Ad updated successfully!"

class AdDeleteView(LoginRequiredMixin, AdOwnerRequiredMixin, DeleteView):
    model = Ad
    template_name = 'ad_confirm_delete.html'
    pk_url_kwarg = 'ad_id'
    success_url = reverse_lazy('ad_list')

class StartConversationView(LoginRequiredMixin, View):
    def get(self, request, ad_id, *args, **kwargs):
        ad = self._get_active_ad_or_404(ad_id)
        owner_user = ad.user
        buyer_user = request.user

        if self._is_owner_starting_conversation(owner_user, buyer_user):
            return self._redirect_to_ad_conversations(ad.id)

        conversation = self._get_or_create_conversation(ad, owner_user, buyer_user)
        return self._redirect_to_conversation_detail(conversation.pk)

    def _get_active_ad_or_404(self, ad_id):
        return get_object_or_404(Ad, pk=ad_id, is_active=True)

    def _is_owner_starting_conversation(self, owner_user, buyer_user):
        return owner_user == buyer_user

    def _redirect_to_ad_conversations(self, ad_id):
        return redirect('conversation_list_for_ad', ad_id=ad_id)

    def _get_or_create_conversation(self, ad, owner_user, buyer_user):
        conversation, _ = Conversation.objects.get_or_create(
            ad=ad,
            owner=owner_user,
            buyer=buyer_user
        )
        return conversation

    def _redirect_to_conversation_detail(self, conversation_id):
        return redirect('conversation_detail', conversation_id=conversation_id)

class ConversationListView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'conversations/list.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        current_user = self.request.user
        return self._get_user_conversations(current_user)

    def _get_user_conversations(self, user):
        return (
            Conversation.objects
            .filter(self._get_user_filter(user))
            .select_related('ad', 'buyer', 'ad__user')
            .annotate(other_username=self._get_other_username_annotation(user))
            .order_by('-created_at')
        )

    def _get_user_filter(self, user):
        return Q(ad__user=user) | Q(buyer=user)

    def _get_other_username_annotation(self, user):
        return Case(
            When(ad__user=user, then=F('buyer__username')),
            default=F('ad__user__username'),
        )

class ConversationDetailView(LoginRequiredMixin, DetailView):
    model = Conversation
    template_name = 'conversations/detail.html'
    context_object_name = 'conversation'
    pk_url_kwarg = 'conversation_id'

    def dispatch(self, request, *args, **kwargs):
        conversation = self.get_object()
        if request.user not in (conversation.owner, conversation.buyer):
            return HttpResponseForbidden("You don't have access to this conversation.")

        Message.objects.filter(
            conversation=conversation,
            read=False
        ).exclude(sender=request.user).update(read=True)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.object
        context['messages'] = conversation.messages.select_related('sender').all()
        context['form'] = MessageForm()
        context["other_user"] = conversation.other_user(self.request.user)
        return context


class SendMessageView(LoginRequiredMixin, View):
    def post(self, request, conversation_id, *args, **kwargs):
        conversation = self._get_conversation_or_forbidden(conversation_id, request.user)
        if isinstance(conversation, JsonResponse):
            return conversation

        message_form = MessageForm(request.POST)

        if message_form.is_valid():
            message = self._create_message(message_form, conversation, request.user)
            return self._build_success_response(message)

        return self._build_error_response(message_form)

    def _get_conversation_or_forbidden(self, conversation_id, user):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if user not in (conversation.owner, conversation.buyer):
            return JsonResponse({'error': 'forbidden'}, status=403)
        return conversation

    def _create_message(self, message_form, conversation, sender):
        message = message_form.save(commit=False)
        message.conversation = conversation
        message.sender = sender
        message.sent_at = timezone.now()
        message.save()
        return message

    def _build_success_response(self, message):
        return JsonResponse({
            'id': message.pk,
            'sender': message.sender.username,
            'content': message.content,
            'sent_at': message.sent_at.isoformat(),
        })

    def _build_error_response(self, message_form):
        return JsonResponse({'errors': message_form.errors}, status=400)

class ConversationMessagesJSONView(LoginRequiredMixin, View):
    def get(self, request, conversation_id, *args, **kwargs):
        conversation = self._get_conversation_or_forbidden(conversation_id, request.user)
        if isinstance(conversation, JsonResponse):
            return conversation

        after_param = request.GET.get('after')
        all_messages_queryset = self._get_all_messages(conversation)
        updated_or_new_messages_queryset = self._get_updated_or_new_messages(conversation, after_param)

        all_message_ids = self._get_message_ids(all_messages_queryset)
        serialized_messages = self._serialize_messages(updated_or_new_messages_queryset)

        return JsonResponse({
            'messages': serialized_messages,
            'all_ids': all_message_ids
        })

    def _get_conversation_or_forbidden(self, conversation_id, current_user):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if current_user not in (conversation.owner, conversation.buyer):
            return JsonResponse({'error': 'forbidden'}, status=403)
        return conversation

    def _get_all_messages(self, conversation):
        return conversation.messages.select_related('sender').all().order_by('sent_at')

    def _get_updated_or_new_messages(self, conversation, after_param):
        messages_queryset = conversation.messages.select_related('sender').all()
        if not after_param:
            return messages_queryset
        after_datetime = parse_datetime(after_param)
        if after_datetime:
            return messages_queryset.filter(
                Q(sent_at__gt=after_datetime) | Q(updated_at__gt=after_datetime)
            )
        return messages_queryset.none()

    def _get_message_ids(self, messages_queryset):
        return list(messages_queryset.values_list('pk', flat=True))

    def _serialize_messages(self, messages_queryset):
        return [
            {
                'id': message.pk,
                'sender': message.sender.username,
                'sender_id': message.sender_id,
                'content': message.content,
                'sent_at': message.sent_at.isoformat(),
                'updated_at': message.updated_at.isoformat() if message.updated_at else None,
                'read': message.read
            }
            for message in messages_queryset
        ]

class AdConversationListView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'conversations/ad_conversations.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        ad_id = self.kwargs['ad_id']
        self.ad = get_object_or_404(Ad, pk=ad_id)
        if self.ad.user != self.request.user:
            return Conversation.objects.none()  # or raise 403
        return self.ad.conversations.select_related('buyer').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ad'] = self.ad
        return context

@method_decorator(require_http_methods(["POST"]), name='dispatch')
class UpdateMessageView(LoginRequiredMixin, View):
    def post(self, request, message_id, *args, **kwargs):
        message = self._get_message_or_forbidden(message_id, request.user)
        if isinstance(message, JsonResponse):
            return message

        new_content = self._get_validated_content(request)
        if isinstance(new_content, JsonResponse):
            return new_content

        self._update_message_content(message, new_content)
        return self._build_success_response(message)

    def _get_message_or_forbidden(self, message_id, current_user):
        message = get_object_or_404(Message, pk=message_id)
        if message.sender != current_user:
            return JsonResponse({'error': 'forbidden'}, status=403)
        return message

    def _get_validated_content(self, request):
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'error': 'Content cannot be empty.'}, status=400)
        return content

    def _update_message_content(self, message, new_content):
        message.content = new_content
        message.save()

    def _build_success_response(self, message):
        return JsonResponse({
            'id': message.pk,
            'content': message.content,
            'sent_at': message.sent_at.isoformat(),
            'updated_at': message.updated_at.isoformat(),
        })

@method_decorator(require_http_methods(["POST"]), name='dispatch')
class DeleteMessageView(LoginRequiredMixin, View):
    def post(self, request, message_id, *args, **kwargs):
        message = self._get_message_or_forbidden(message_id, request.user)
        if isinstance(message, JsonResponse):
            return message

        self._delete_message(message)
        return self._build_success_response(message_id)

    def _get_message_or_forbidden(self, message_id, current_user):
        message = get_object_or_404(Message, pk=message_id)
        if message.sender != current_user:
            return JsonResponse({'error': 'forbidden'}, status=403)
        return message

    def _delete_message(self, message):
        message.delete()

    def _build_success_response(self, message_id):
        return JsonResponse({'success': True, 'id': message_id})

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_user(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_user()
        conversations = self._get_user_conversations(user)

        for conv in conversations:
            conv.has_unread = conv.has_unread_for(user)

        context["user_obj"] = user
        context["conversations"] = conversations
        return context

    def _get_user_conversations(self, user):
        return (
            Conversation.objects.filter(
                Q(owner=user) | Q(buyer=user)
            )
            .select_related("ad", "owner", "buyer")
            .annotate(
                other_username=Case(
                    When(owner=user, then=F("buyer__username")),
                    default=F("owner__username")
                )
            )
            .order_by("-created_at")
        )
