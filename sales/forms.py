# forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import Ad, AdImage

class AdForm(forms.ModelForm):
    class Meta:
        model = Ad
        fields = [
            'title', 'description', 'price', 'location',
            'contact_info', 'contact_info_visible',
            'category', 'event_date'
        ]

class AdImageForm(forms.ModelForm):
    class Meta:
        model = AdImage
        fields = ['image']

AdImageFormSet = inlineformset_factory(
    Ad,
    AdImage,
    form=AdImageForm,
    extra=3,        # Show 3 image fields by default
    can_delete=True # Allow removing images in update view
)
