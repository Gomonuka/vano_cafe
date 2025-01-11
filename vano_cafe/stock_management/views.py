from django.contrib import messages
from django.shortcuts import render
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .models import Product, Order, User
from django.db import transaction
from django.db.models import F
from .products_data import PRODUCTS
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from stock_management.forms import ProductForm, CustomUserEditForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
#Custom login view
def custom_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            #Redirect based on user role
            if user.is_admin():
                return redirect('admin_dashboard')
            else:
                return redirect('order_creation')
    else:
        form = AuthenticationForm() #Rendering an empty login form
    return render(request, 'login.html', {'form': form})
#Order creation view
def order_creation(request):
    filtered_products = {}  #Dictionary to store products available for ordering
    products_max_quantity = {}   #Dictionary to store the maximum orderable quantity of each product

    for category, products in PRODUCTS.items(): #Loop through product categories
        filtered_products[category] = {}
        for product_name, details in products.items():
            ingredients = details["ingredients"]    #Get the product's ingredient requirements
            try:
                #Determine the maximum quantity that can be ordered based on ingredient stock
                max_quantity = min(
                    Product.objects.get(name=ingredient).stock // required_amount
                    for ingredient, required_amount in ingredients.items()
                )
                if max_quantity > 0:
                    # Add the product to the filtered list if it can be ordered (there are enough ingredients in stock)
                    filtered_products[category][product_name] = details
                    products_max_quantity[product_name] = max_quantity
            except Product.DoesNotExist as e:
                # Log an error if an ingredient does not exist in the database
                print(f"Ingredient not found: {e}")
                continue

    if request.method == "POST":
        products_to_add = []    # List to store products being added to the order
        
        for key, value in request.POST.items(): #Parse POST data for product quantities
            if key.startswith("products-quantity-"):    #Identify keys representing product quantities
                product_name_key = key.replace("products-quantity-", "products-name-")
                quantity = int(value)   #Extract the quantity for the product
                product_name = request.POST.get(product_name_key)

                if quantity > 0:
                    #Validate and process the selected product
                    for category, product_data in PRODUCTS.items():
                        if product_name in product_data:
                            ingredients = product_data[product_name]["ingredients"]
                            price = product_data[product_name]["price"]
                            # Check if sufficient stock is available for all required ingredients
                            for ingredient, required_amount in ingredients.items():
                                product = Product.objects.get(name=ingredient)
                                if product.stock < required_amount * quantity:
                                    messages.error(request, f"Not enough stock for {ingredient}")
                                    return redirect("create_order")
                            #Add the validated product to the order list
                            products_to_add.append({
                                "name": product_name,
                                "quantity": quantity,
                                "price": price,
                            })
                            break
        #Calculating the total price for the order                    
        total_price = sum(product["price"] * product["quantity"] for product in products_to_add)
        #Deduct stock for each ingredient in the ordered products
        for product in products_to_add:
            product_name = product["name"]
            quantity = product["quantity"]
            ingredients = next(
                prod[product_name]["ingredients"]
                for cat, prod in PRODUCTS.items()
                if product_name in prod
            )
            for ingredient, required_amount in ingredients.items():
                product_obj = Product.objects.get(name=ingredient)
                product_obj.stock -= required_amount * quantity
                product_obj.save()

        order = Order.objects.create(
            barista=request.user,
            status="paid",
            total_price=total_price,
            products=products_to_add,
        )

        messages.success(request, "Order successfully created!")
        return redirect("order_queue")
    #Render the order creation page with filtered products and their maximum quantities
    return render(request, "order_creation.html", {
        "PRODUCTS": filtered_products,
        "products_max_quantity": products_max_quantity,
    })
#Order queue view
def order_queue(request):
    #Retrieve all orders with the status "paid"
    orders = Order.objects.filter(status="paid")

    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        order = Order.objects.get(id=order_id)
        #Mark the order as ready if it is not already marked as such
        if action == "mark_ready" and order.status != 'ready':
            order.status = 'ready'
            order.save()

        elif action == "cancel_order" and order.status != 'cancelled':
            #Cancel the order if it is not already cancelled
            order.status = 'cancelled'

            try:
                #Use a database transaction to ensure stock updates are atomic
                with transaction.atomic():
                    for product in order.products:  
                        print(f"Processing product: {product}") 
                        product_name = product.get('name')
                        quantity = product.get('quantity')
                        # Retrieve the product object and update its stock
                        if product_name and quantity:
                            try:
                                product_obj = Product.objects.get(name=product_name.strip().lower())
                                print(f"Found product: {product_obj}")
                                product_obj.stock += quantity   #Add the quantity back to the stock
                                product_obj.save()
                            except Product.DoesNotExist:
                                print(f"Error: Product {product_name} does not exist in the database.")
                        else:
                            print(f"Invalid product data: {product}")

                    order.save()
                    print(f"Order {order.id} has been cancelled and stock updated.") 
            except Exception as e:
                print(f"Error during order cancellation: {e}")

        return redirect('order_queue') 
    #Parse the product details for each order for display in the template
    for order in orders:
        order.parsed_products = []
        for product in order.products: 
            product_name = product.get('name')
            quantity = product.get('quantity')
            price = product.get('price')
            # Append the parsed product details to the list
            order.parsed_products.append({
                "name": product_name,
                "quantity": quantity,
                "price": price,
            })

    return render(request, "order_queue.html", {"orders": orders})
#View for displaying the order history
def order_history(request):
    #Retrieve orders that have the status 'ready' and 'cancelled'
    ready_orders = Order.objects.filter(status='ready')
    cancelled_orders = Order.objects.filter(status='cancelled')
    
    return render(request, 'order_history.html', {
        'ready_orders': ready_orders,
        'cancelled_orders': cancelled_orders,
    })
#Admin dashboard view to monitor order and product data
def admin_dashboard(request):
    if not request.user.is_admin():
        return redirect('login')
    #Retrieve products with stock less than or equal to their low stock threshold
    low_stock_products = Product.objects.filter(stock__lte=F('low_stock_threshold'))
    #Retrieve orders with status 'ready' for data analysis
    orders = Order.objects.filter(status='ready')
    #Calculate the total sales amount from the ready orders
    total_sales = sum(order.total_price for order in orders)
    #Calculate the average order value (total sales divided by number of orders)
    avg_order_value = total_sales / orders.count() if orders.exists() else 0
    avg_order_value = format(avg_order_value, ".2f")
    #Create a dictionary to track the total quantity sold for each product
    product_sales = {}
    for order in orders:
        for product in order.products: 
            product_name = product.get('name')
            quantity = product.get('quantity', 0)  #0 is a default value that will be returned if the product dictionary does not contain the key 'quantity'
            if product_name:
                #Add the quantity sold to the total for the product
                product_sales[product_name] = product_sales.get(product_name, 0) + quantity
    #Sort the product sales dictionary by quantity sold in descending order
    most_popular_products = dict(sorted(product_sales.items(), key=lambda x: x[1], reverse=True))
    #If there are product sales data, generate a bar chart
    if product_sales:
        product_names = list(product_sales.keys()) #List of product names
        product_quantities = list(product_sales.values())   #List of quantities of products
        #Create a bar chart using matplotlib
        plt.figure(figsize=(10, 6))
        plt.bar(product_names, product_quantities, color='purple')
        plt.xlabel('Products')
        plt.ylabel('Quantity Sold')
        plt.title('Product Sales')
        plt.xticks(rotation=45, ha='right')
        #Save the plot to a buffer and convert it to base64 for embedding in the template
        buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png')
        plt.close()
        buffer.seek(0)
        #Encode the image data as base64
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        buffer.close()
    else:
        #If no product sales data, set image_data to None
        image_data = None
    #Prepare the context to be passed to the template
    context = {
        'total_sales': total_sales,
        'avg_order_value': avg_order_value,
        'most_popular_products': most_popular_products,
        'sales_chart': image_data,
        'low_stock_products': low_stock_products,
    }

    return render(request, 'admin_dashboard.html', context)
#View for managing stock (list all products)
def stock_management(request):
    if not request.user.is_admin():
        return redirect('login')
    #Retrieve all products from the database
    products = Product.objects.all()
    return render(request, 'stock_management.html', {'products': products})
#View for creating a new product in stock
def stock_create(request):
    if request.method == 'POST':
        #Initialize the custom form with POST data
        form = ProductForm(request.POST)
         #If the form is valid, save the product and redirect to stock management
        if form.is_valid():
            form.save()
            return redirect('stock_management')
    else:
        form = ProductForm()
    return render(request, 'stock_form.html', {'form': form, 'action': 'Create'})
#View for updating an existing product in stock
def stock_update(request, pk):
    #Retrieve the product based on the primary key (pk), or return a 404 error if not found
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        #Same form as for product creation
        form = ProductForm(request.POST, instance=product)
        #If the form is valid, save the updated product and redirect to stock management
        if form.is_valid():
            form.save()
            return redirect('stock_management')
    else:
        form = ProductForm(instance=product)
    return render(request, 'stock_form.html', {'form': form, 'action': 'Update'})
#View for confirming the deletionn of a product from stock
def stock_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('stock_management')
    return render(request, 'stock_confirm_delete.html', {'product': product})
# View for managing system's users (list all users)
def user_management(request):
    if not request.user.is_admin():
        return redirect('login') 
    # Retrieve all users from the database
    users = User.objects.all()
    return render(request, 'user_management.html', {'users': users})
#A mixin to enforce that the user must be an admin to access the associated views
class AdminRequiredMixin(UserPassesTestMixin):
    #Override the test_func method to check if the user is an admin
    def test_func(self):
        return self.request.user.is_admin()
#View for listing all users, accessible only by authenticated admins
class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User    #The model this view works with
    template_name = 'user_list.html'    #Template to render the list of users
    context_object_name = 'users'   #The context variable name for the list of users
# View for creating a new user, accessible only by authenticated admins
class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = User
    fields = ['username', 'role', 'password']   #Fields to be shown in the form
    template_name = 'user_form.html'
    success_url = reverse_lazy('user_management')
    #Override the form_valid method to hash the user's password before saving
    def form_valid(self, form):
        #Set the user's password with the hashed version of the input
        form.instance.set_password(form.cleaned_data['password'])
        #Call the parent class's form_valid method to save the form and return the response
        return super().form_valid(form)
#View for updating an existing user, accessible only by authenticated admins
class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserEditForm     #The form class used to edit the user
    template_name = 'user_form.html'    #Template for the user edit form
    success_url = reverse_lazy('user_management')   #Redirect to user management after successful update
    #View for handling the update process, separate from the class-based view
    def edit_user(request, pk):
        user = get_object_or_404(User, pk=pk)
        if request.method == 'POST':
            form = CustomUserEditForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                return redirect('user_management')
        else:
            form = CustomUserEditForm(instance=user)

        return render(request, 'edit_user.html', {'form': form, 'user': user})
#View for deleting a user, accessible only by authenticated admins
class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'user_confirm_delete.html'
    success_url = reverse_lazy('user_management')
#View for displaying products, either by category or all categories
def display_products(request, category=None):
    """
    View to display products by category. If no category is specified, show all categories.
    """
    #If a category is specified, show products for that category
    if category:
        #Retrieve the products for the specified category from the PRODUCTS data
        products = PRODUCTS.get(category, {})
        #If the category does not exist in the PRODUCTS data, show an error
        if not products:
            return render(request, "error.html", {"message": "Category not found."})
        #Context to pass the category and its products to the template
        context = {"category": category, "products": products}
    else:
        #If no category is specified, pass the list of all categories to the template
        context = {"categories": PRODUCTS.keys()}
    
    return render(request, "order_creation.html", context)