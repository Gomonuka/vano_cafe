from django import forms
from .models import Product, User
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.hashers import make_password

# Form used for creating and editing products
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'unit', 'price', 'stock', 'low_stock_threshold']
# Custom user edit form to allow editing of user details, including the password
class CustomUserEditForm(UserChangeForm):
    # Overriding the default password field to provide a new widget and placeholder
    password = forms.CharField(
        required=False, #do not have to change the password
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password (optional)'}),
        help_text="Leave blank if you don't want to change the password."
    )

    class Meta:
        model = User
        fields = ['username', 'role', 'password']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_password(self):
        """Prevent resetting the password unless explicitly updated."""
        """
        Custom method to clean and validate the password field.
        - If the password is provided, hash it using `make_password`.
        - If left blank, retain the current password for the user.
        """
        password = self.cleaned_data.get('password')
        if password:
            return make_password(password)
        return self.instance.password
