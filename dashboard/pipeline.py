import io

import urllib3
from django.core.files import File
from django.shortcuts import redirect
from social_core.pipeline.partial import partial

from .models import Company, User


def retrieve_image(url):
    response = urllib3.PoolManager().urlopen('GET', url,
                                             preload_content=False).read()
    return io.BytesIO(response)


@partial
def identify_company(strategy, backend, request, details, *args, **kwargs):
    company_id = strategy.session_get('company_id', None)
    if not company_id:
        return redirect('register_social')

    user = User.objects.get(email=kwargs['response']['email'])
    company = Company.objects.get(id=company_id)
    user.employee.location = company.location_set.first()
    user.employee.username = kwargs['username']
    file_name = 'user_{0}.jpg'.format(user.id)
    user.employee.image.save(file_name, File(
        retrieve_image(kwargs['response']['picture'])))
    user.employee.save()
    return
