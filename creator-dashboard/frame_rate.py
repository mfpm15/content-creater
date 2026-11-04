"""Video Studio frame rates. Old plans without fps retain their original 30 fps."""
RATES = (30, 60)
DEFAULT = 60


def validate(value):
    if type(value) is not int or value not in RATES:
        raise ValueError('FPS harus bilangan bulat 30 atau 60')
    return value


def get(plan):
    return validate(plan.get('fps', 30))
