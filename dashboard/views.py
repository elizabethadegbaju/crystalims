from builtins import ValueError, TypeError, OverflowError

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from .models import *
from .render import Render
from .tokens import account_activation_token


def home(request):
    return render(request, 'index.html')


@login_required
def dashboard(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        most_requested = Item.objects.filter(
            company=company).annotate(
            num_allocations=Count('allocation')).order_by('-num_allocations')[
                         :10]
        assets_value = Item.objects.filter(
            company=company).aggregate(Sum('price'))
        pending_requests = Allocation.objects.filter(
            item__company=company,
            approver_id=1).count()
        pending_items = Allocation.objects.filter(
            item__company=company,
            approver_id=1).order_by(
            'item_id').distinct().count()  # there can be multiple requests on one item
        allocated_items = Allocation.objects.filter(
            item__company=company, approved=True,
            checked_in=False,
            start_date__lte=timezone.now().date()).count()
        items_count = Item.objects.filter(
            company=company).count()
        free_items = items_count - (
                pending_items + allocated_items)
        categories = Category.objects.filter(company=company).annotate(
            Count('item'))
        categories_count = categories.count()
        alerts, unread_messages = unread_messages_notification(user)
        assets_monthly_value = company.assetlog_set.filter(
            year=timezone.now().year)
        excellent_condition = Item.objects.filter(
            company=company, condition='E').count()
        good_condition = Item.objects.filter(company=company,
                                             condition='G').count()
        fair_condition = Item.objects.filter(company=company,
                                             condition='F').count()
        very_poor_condition = Item.objects.filter(
            company=company, condition='VP').count()
        if items_count != 0:
            excellent_condition_percentage = round(
                (excellent_condition / items_count) * 100, 1)
            good_condition_percentage = round(
                (good_condition / items_count) * 100, 1)
            fair_condition_percentage = round(
                (fair_condition / items_count) * 100, 1)
            very_poor_condition_percentage = round(
                (very_poor_condition / items_count) * 100, 1)
        else:
            excellent_condition_percentage = 0
            good_condition_percentage = 0
            fair_condition_percentage = 0
            very_poor_condition_percentage = 0
        year = timezone.now().year
        assets_mv = {}
        for monthly_value in assets_monthly_value:
            assets_mv[monthly_value.month] = monthly_value.assets
        context = {'company': company,
                   'unread_messages': unread_messages,
                   'alerts': alerts,
                   'most_requested': most_requested,
                   'assets_value': assets_value,
                   'items_count': items_count,
                   'pending_requests': pending_requests,
                   'pending_items': pending_items,
                   'allocated_items': allocated_items,
                   'free_items': free_items,
                   'categories': categories,
                   'categories_count': categories_count,
                   'assets_mv': assets_mv,
                   'excellent_condition_percentage': excellent_condition_percentage,
                   'good_condition_percentage': good_condition_percentage,
                   'fair_condition_percentage': fair_condition_percentage,
                   'very_poor_condition_percentage': very_poor_condition_percentage,
                   'year': year}
        return render(request, 'dashboard.html', context)
    else:
        return redirect('profile')


def signup(request):
    if request.method == "GET":
        companies = Company.objects.all().order_by('name')
        return render(request, 'registration/register.html',
                      {'companies': companies})
    elif request.method == "POST":
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password = request.POST['password']
        company_id = request.POST['company']
        company = Company.objects.get(id=company_id)
        image = request.FILES['profile_pic']

        user = User.objects.create_user(email, password)
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = False
        user.save()
        send_activation_email(company, email, request, user)
        user.employee.location = company.location_set.first()
        user.employee.username = first_name[:3] + "_" + last_name[:3]
        user.employee.image = image
        user.employee.save()
        return HttpResponse(
            'Account has been created successfully. Look out for the verification link sent to your email address.')


def send_activation_email(company, email, request, user):
    current_site = get_current_site(request)
    mail_subject = 'Verify your {0} employee account on Crystal.'.format(
        company.name)
    message = render_to_string('acc_activate_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': account_activation_token.make_token(user),
    })
    to_email = email
    send_mail(mail_subject, message, from_email="no-reply@crystalims.com",
              recipient_list=[to_email],
              fail_silently=False, )


def social_signup(request):
    if request.method == "GET":
        companies = Company.objects.all().order_by('name')
        return render(request, 'registration/register_social.html',
                      {'companies': companies})
    elif request.method == "POST":
        request.session['company_id'] = request.POST['company_id']
        return redirect(reverse('social:complete', args=("google-oauth2",)))


@login_required
def items(request):
    if request.method == "GET":
        user = request.user
        alerts, unread_messages = unread_messages_notification(user)
        company = user.employee.location.company

        items_list = Item.objects.filter(
            company=company).order_by(
            'description')
        items = pager(items_list, request)
        return render(request, 'items.html',
                      {'company': company, 'items': items,
                       'unread_messages': unread_messages,
                       'alerts': alerts})


def pager(list, request):
    if "num" in request.GET.keys():
        number = int(request.GET["num"])
    else:
        number = 10
    paginator = Paginator(list, number)
    page = request.GET.get('page')
    items = paginator.get_page(page)
    return items


def unread_messages_notification(user):
    unread_messages = user.inbox_messages.filter(from_user_id__gte=2,
                                                 read=False).order_by(
        '-date_sent')
    alerts = user.inbox_messages.filter(from_user_id=1, read=False).order_by(
        '-date_sent')
    return alerts, unread_messages


def item(request, pk):
    user = request.user
    company = request.user.employee.location.company
    if request.method == "GET":
        item = Item.objects.get(SKU=pk)
        allocations = item.allocation_set.all()
        categories = company.category_set.all()
        suppliers = company.supplier_set.all()
        alerts, unread_messages = unread_messages_notification(user)
        return render(request, 'item.html',
                      {'item': item, 'allocations': allocations,
                       'unread_messages': unread_messages, 'alerts': alerts,
                       'categories': categories, 'suppliers': suppliers})


@login_required
def profile(request):
    if request.method == "GET":
        user = request.user
        alerts, unread_messages = unread_messages_notification(user)
        allocations = user.item_allocations.all()
        return render(request, 'profile.html', {'allocations': allocations,
                                                'unread_messages': unread_messages,
                                                'alerts': alerts})


def create(request):
    if request.method == "GET":
        return render(request, 'registration/register_company.html')
    elif request.method == "POST":
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password = request.POST['password']
        company_name = request.POST['company_name']
        company_address = request.POST['company_address']
        company_city = request.POST['company_city']
        company_country = request.POST['company_country']
        image = request.FILES['profile_pic']

        company = Company.objects.create(name=company_name)
        company.save()
        location = Location.objects.create(company=company,
                                           address=company_address,
                                           city=company_city,
                                           country=company_country,
                                           name=company_city)
        location.save()
        user = User.objects.create_user(email, password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        user.employee.location.company = Company.objects.get(id=company.id)
        user.employee.location = Location.objects.get(id=location.id)
        user.employee.username = first_name[:3] + "_" + last_name[:3]
        user.employee.image = image
        user.employee.save()
        user.groups.set([1])

        return redirect('login')


@login_required
def team(request):
    user = request.user
    alerts, unread_messages = unread_messages_notification(user)

    team_list = Employee.objects.filter(
        location__company=user.employee.location.company).order_by(
        '-user__last_login')
    team = pager(team_list, request)
    return render(request, 'team.html',
                  {'team': team, 'unread_messages': unread_messages,
                   'alerts': alerts})


def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.groups.set([3])
        user.is_active = True
        user.save()
        login(request, user, 'django.contrib.auth.backends.ModelBackend')
        return redirect(profile)
    else:
        return HttpResponse('Activation link is invalid!')


@login_required
def team_member(request, pk):
    if request.method == "GET":
        user = User.objects.get(id=pk)
        logged_in_user = request.user
        alerts, unread_messages = unread_messages_notification(user)
        if user.employee.location.company_id == logged_in_user.employee.location.company_id:
            allocations = user.item_allocations.all()
            return render(request, 'profile.html', {'allocations': allocations,
                                                    'unread_messages': unread_messages,
                                                    'alerts': alerts,
                                                    'user': user})
        else:
            return redirect('page_not_found')


def error(request):
    user = request.user
    alerts, unread_messages = unread_messages_notification(user)
    return render(request, '404.html',
                  {'unread_messages': unread_messages, 'alerts': alerts})


@login_required
def image_upload(request):
    image = request.FILES['profile_pic']
    user = request.user
    user.employee.image.delete()
    user.employee.image = image
    user.employee.save()
    return redirect('profile')


def error_404_view(request, exception):
    data = {"name": "crystal-ims.appspot.com"}
    return render(request, '404.html', data)


@login_required
def edit_user(request):
    username = request.POST['username']
    email = request.POST['email']
    first_name = request.POST['first_name']
    last_name = request.POST['last_name']
    user = request.user

    user.employee.username = username
    user.employee.save()
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.save()
    return redirect('profile')


@login_required
def add_employee(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            alerts, unread_messages = unread_messages_notification(user)
            locations = company.location_set.all()
            return render(request, 'add_employee.html',
                          {'locations': locations,
                           'unread_messages': unread_messages,
                           'alerts': alerts})
        elif request.method == "POST":
            f_name = request.POST['first_name']
            l_name = request.POST['last_name']
            email = request.POST['email']
            location = request.POST['location']
            new_user = User.objects.create_user(email=email,
                                                password="{0}%{1}".format(
                                                    f_name, l_name))
            new_user.first_name = f_name
            new_user.last_name = l_name
            new_user.save()
            new_user.employee.location = location
            new_user.employee.save()
            send_activation_email(company, email, request, new_user)
            return redirect('team')
    else:
        return redirect('team')


@login_required
def add_item(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            alerts, unread_messages = unread_messages_notification(user)
            categories = company.category_set.all()
            suppliers = company.supplier_set.all()
            return render(request, 'add_item.html',
                          {'categories': categories, 'suppliers': suppliers,
                           'unread_messages': unread_messages,
                           'alerts': alerts})
        elif request.method == "POST":
            SKU = request.POST['SKU']
            description = request.POST['description']
            price = request.POST['price']
            quantity = request.POST['quantity']
            supplier = request.POST['supplier']
            category = request.POST['category']
            company = request.user.employee.location.company
            item = Item.objects.create(SKU=SKU,
                                       description=description,
                                       price=price,
                                       supplier_id=supplier,
                                       quantity=quantity,
                                       condition='E',
                                       category_id=category,
                                       company=company)
            item.save()
            return redirect('items')
    else:
        return redirect('items')


@login_required
def allocations(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        alerts, unread_messages = unread_messages_notification(user)
        allocations = Allocation.objects.filter(
            item__company=user.employee.location.company)
        return render(request, 'allocations.html', {'allocations': allocations,
                                                    'unread_messages': unread_messages,
                                                    'alerts': alerts})
    else:
        return redirect('dashboard')


@login_required
def add_category(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            alerts, unread_messages = unread_messages_notification(user)
            return render(request, 'add_category.html',
                          {'unread_messages': unread_messages,
                           'alerts': alerts})
        elif request.method == "POST":
            name = request.POST['category']
            category = Category.objects.create(name=name, company=company)
            category.save()
            return redirect('add_category')


@login_required
def messages(request):
    user = request.user
    employees = Employee.objects.filter(
        location__company=user.employee.location.company).order_by(
        'user__first_name')
    alerts, unread_messages = unread_messages_notification(user)
    inbox = user.inbox_messages.filter(from_user_id__gte=2).order_by(
        '-date_sent')
    sent = user.sent_messages.all()
    return render(request, 'messages.html',
                  {'inbox': inbox, 'sent': sent,
                   'unread_messages': unread_messages, 'alerts': alerts,
                   'employees': employees})


@login_required
def add_location(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            alerts, unread_messages = unread_messages_notification(user)
            return render(request, 'add_location.html',
                          {'unread_messages': unread_messages,
                           'alerts': alerts})
        elif request.method == "POST":
            name = request.POST['name']
            address = request.POST['address']
            city = request.POST['city']
            country = request.POST['country']
            location = Location.objects.create(name=name, address=address,
                                               city=city,
                                               country=country,
                                               company=company)
            location.save()
            return redirect('add_location')


@login_required
def pdf(request):
    user = request.user
    company = user.employee.location.company
    most_requested = Item.objects.filter(
        location__company=company).annotate(
        num_allocations=Count('allocation')).order_by('-num_allocations')[
                     :10]
    assets_value = Item.objects.filter(
        location__company=company).aggregate(Sum('price'))
    pending_requests = Allocation.objects.filter(
        item__location__company=company,
        approver__isnull=True).count()
    pending_items = Allocation.objects.filter(
        item__location__company=company,
        approver__isnull=True).order_by(
        'item_id').distinct().count()
    allocated_items = Allocation.objects.filter(
        item__location__company=company, approved=True,
        checked_in=False,
        start_date__lte=timezone.now().date()).count()
    items_count = Item.objects.filter(
        location__company=company).count()
    free_items = items_count - (
            pending_items + allocated_items)
    categories_count = Category.objects.filter(company=company).count()
    assets_monthly_value = AssetLog.objects.filter(company=company,
                                                   year=timezone.now().year)
    excellent_condition = Item.objects.filter(location__company=company,
                                              condition='E').count()
    excellent_condition_percentage = round(
        (excellent_condition / items_count) * 100, 1)
    good_condition = Item.objects.filter(location__company=company,
                                         condition='G').count()
    good_condition_percentage = round(
        (good_condition / items_count) * 100, 1)
    fair_condition = Item.objects.filter(location__company=company,
                                         condition='F').count()
    fair_condition_percentage = round(
        (fair_condition / items_count) * 100, 1)
    very_poor_condition = Item.objects.filter(location__company=company,
                                              condition='VP').count()
    very_poor_condition_percentage = round(
        (very_poor_condition / items_count) * 100, 1)
    assets_mv = {}
    for monthly_value in assets_monthly_value:
        assets_mv[monthly_value.month] = monthly_value.assets
    params = {'request': request,
              'company': company,
              'most_requested': most_requested,
              'assets_value': assets_value,
              'items_count': items_count,
              'pending_requests': pending_requests,
              'pending_items': pending_items,
              'allocated_items': allocated_items,
              'free_items': free_items,
              'categories_count': categories_count,
              'assets_mv': assets_mv,
              'excellent_condition_percentage': excellent_condition_percentage,
              'good_condition_percentage': good_condition_percentage,
              'fair_condition_percentage': fair_condition_percentage,
              'very_poor_condition_percentage': very_poor_condition_percentage}
    return Render.render('dashboard.html', params)


@login_required
def message(request, pk):
    user = request.user
    alerts, unread_messages = unread_messages_notification(user)
    message = Message.objects.get(pk=pk)
    if (user == message.to_user) | (user == message.from_user):
        if user == message.to_user:
            message.read = True
            message.save()
        return render(request, 'message.html',
                      {'unread_messages': unread_messages, 'alerts': alerts,
                       'message': message})
    else:
        return redirect('page_not_found')


@login_required
def send_message(request):
    to_user = request.POST['to_user']
    message = request.POST['message']
    user = request.user
    Message.objects.create(to_user_id=to_user, text=message,
                           from_user_id=user.id)
    return redirect('messages')


@login_required
def place_order(request):
    quantity = request.GET['quantity']
    item_id = request.GET['item']
    item = Item.objects.get(id=item_id)
    item.order(quantity)
    return None


def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request,
                             'Your password was successfully updated!')
            return redirect('change_password')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'registration/password_change_form.html', {
        'form': form
    })


def verify(request, pk):
    user = User.objects.get(id=pk)
    user.groups.set([3])
    return redirect(dashboard)
