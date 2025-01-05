from django import forms
from .models import Product, User
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.hashers import make_password

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'unit', 'price', 'stock', 'low_stock_threshold']

class CustomUserEditForm(UserChangeForm):
    password = forms.CharField(
        required=False,
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
        password = self.cleaned_data.get('password')
        if password:
            return make_password(password)
        return self.instance.password
