from django.contrib.auth.models import AbstractUser
from django.db import models
from ordered_model.models import OrderedModel
from django.urls import reverse

class CustomUser(AbstractUser):
    """
    A custom user model that extends Django's built-in AbstractUser.

    This model adds additional fields for user-specific information
    like contact visibility, a phone number, and a profile picture.
    """

    contact_info_visibility = models.BooleanField(default=False, help_text="Whether the user's contact information is visible")
    phone_number = models.CharField(max_length=15, blank=True, null=True, help_text="The user's contact phone number.")
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, help_text="A profile picture for the user.")

    def __str__(self):
        return self.username
    
class Category(models.Model):
    """
    A model representing a Categories of Each advertisement posted by a user.
    """

    name = models.CharField(max_length=255, unique=True, help_text="The name of the category (e.g., 'Job', 'For Sale').")
    description = models.TextField(blank=True, null=True, help_text="A brief description of the category's purpose.")

    def __str__(self):
        return self.name  

class Ad(models.Model):
    """
    A model representing a single advertisement posted by a user.
    """

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ads', help_text="The user who created this ad.")
    title = models.CharField(max_length=255, help_text="The main title of the advertisement.")
    description = models.TextField(help_text="A detailed description of the ad's content.")
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="The price of the item or service, if applicable.")
    location = models.CharField(max_length=255, help_text="The geographical location associated with the ad.")
    contact_info = models.CharField(max_length=255, help_text="Contact information for the ad, such as an email address or phone number.")
    contact_info_visible = models.BooleanField(default=False, help_text="Controls if the contact information is visible to all users or only the ad's owner.")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='ads', help_text="The category this ad belongs to.")
    event_date = models.DateField(blank=True, null=True, help_text="The date of the event, applicable for 'Event' ads.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="The date and time the ad was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="The date and time the ad was last updated.")
    is_active = models.BooleanField(default=True, help_text="Indicates whether the ad is currently active and visible.")  

    def __str__(self):
        return self.title

    def is_visible_to_user(self, user):
        return self.contact_info_visible or user == self.user

    def get_absolute_url(self):
        return reverse('ad_detail', args=[str(self.pk)])
    
class AdImage(OrderedModel):
    """
    A model to store multiple images for a single Ad.
    This uses OrderedModel to automatically manage the ordering of images.
    """

    ad = models.ForeignKey(
        Ad, 
        on_delete=models.CASCADE, 
        related_name='images',
    )
    image = models.ImageField(
        upload_to='ad_images/',
        help_text="The image file for the ad."
    )
    
    class Meta:
        ordering = ['ad', 'order']

    def __str__(self):
        return f"Image for Ad: {self.ad.title}"

class Conversation(models.Model):
    """
    Unique conversation between ad owner and a buyer, per ad.
    (ad_id, buyer) pair is unique so owner can have multiple buyers.
    """
    ad = models.ForeignKey('Ad', on_delete=models.CASCADE, related_name='conversations', help_text="The advertisement this conversation is about.")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='owned_conversations', editable=False, help_text="The user who owns the ad and participates in this conversation.")
    buyer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='buyer_conversations', help_text="The user interested in the ad (not the owner).")
    created_at = models.DateTimeField(auto_now_add=True, help_text="The date and time this conversation was started.")

    class Meta:
        unique_together = ('ad', 'buyer')
        ordering = ('-created_at',)

    def __str__(self):
        return f"Conversation: Ad({self.ad_id}) owner={self.owner_id} buyer={self.buyer_id}"

    def other_user(self, user):
        return self.buyer if user == self.owner else self.owner

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.buyer == self.ad.user:
            raise ValidationError("A user cannot start a conversation on their own ad.")

    def save(self, *args, **kwargs):
        if not self.pk:
            self.owner = self.ad.user
        super().save(*args, **kwargs)

    def has_unread_for(self, user):
        return self.messages.filter(read=False).exclude(sender=user).exists()

class Message(models.Model):
    """
    Represents a private message sent between two users regarding a specific ad.
    """

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages', help_text="The conversation this message belongs to.")
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages', help_text="The user who sent the message.")
    content = models.TextField(help_text="The content of the message.")
    sent_at = models.DateTimeField(auto_now_add=True, help_text="The date and time the message was sent.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last time the message was updated.")
    read = models.BooleanField(default=False, help_text="Indicates whether the recipient has read the message.") 

    class Meta:
        ordering = ('sent_at',)

    def __str__(self):
        return f"Msg({self.pk}) conv={self.conversation_id} from={self.sender_id}"
