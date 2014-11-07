DEBUG = True
TEMPLATE_DEBUG = True

SECRET_KEY = '01234567890abcdefghijklmnopqrstuvwxyz+-*/!?#()&$%€'

DATABASES = {
    'default': {
        'NAME': 'freelance',
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'USER': 'john',
        'PASSWORD': 'mypasswd',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

INTERNAL_IPS = ['127.0.0.1']
