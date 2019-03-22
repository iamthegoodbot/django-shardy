import os

from pip._internal.req import parse_requirements
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))
with open('req.txt') as f:
    required = f.read().splitlines()

setup(
    name='django-shardy',
    version='0.0.1',
    packages=['shardy', 'shardy.migrations', 'shardy.tests'],
    include_package_data=True,
    license='',  # example license
    description='Sharding db per tenant utils for Django ORM.',
    long_description=README,
    url='https://github.com/iamthegoodbot/django-shardy',
    author='Rouslan Korkmazov',
    author_email='r.korkmazov@sailplay.ru',
    install_requires=required,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 2.1',  # replace "X.Y" as appropriate
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)