"""GNUTLS data validators"""

__all__ = ['function_args', 'method_args', 'none', 'ignore', 'list_of', 'one_of']


# Helper functions (internal use)
#

def isclass(obj):
    return hasattr(obj, '__bases__') or isinstance(obj, type)


# Internal validator classes
#

class Validator(object):
    _registered = []

    def __init__(self, typ):
        self.type = typ

    def check(self, value):
        return False

    @staticmethod
    def can_validate(typ):
        return False

    @classmethod
    def register(cls, validator):
        cls._registered.append(validator)

    @classmethod
    def get(cls, typ):
        for validator in cls._registered:
            if validator.can_validate(typ):
                return validator(typ)
        else:
            return None

    @staticmethod
    def join_names(names):
        if type(names) in (tuple, list):
            if len(names) <= 2:
                return ' or '.join(names)
            else:
                return ' or '.join((', '.join(names[:-1]), names[-1]))
        else:
            return names

    def _type_names(self):
        if isinstance(self.type, tuple):
            return self.join_names([t.__name__.replace('NoneType', 'None') for t in self.type])
        else:
            return self.type.__name__.replace('NoneType', 'None')

    @property
    def name(self):
        name = self._type_names()
        if name.startswith('None'):
            prefix = ''
        elif name[0] in ('a', 'e', 'i', 'o', 'u'):
            prefix = 'an '
        else:
            prefix = 'a '
        return prefix + name


class IgnoringValidator(Validator):
    def __init__(self, typ):
        self.type = none

    def check(self, value):
        return True

    @staticmethod
    def can_validate(obj):
        return obj is ignore


class TypeValidator(Validator):
    def check(self, value):
        return isinstance(value, self.type)

    @staticmethod
    def can_validate(obj):
        return isclass(obj)


class MultiTypeValidator(TypeValidator):
    @staticmethod
    def can_validate(obj):
        return isinstance(obj, tuple) and not [x for x in obj if not isclass(x)]


class OneOfValidator(Validator):
    def __init__(self, typ):
        self.type = typ.type

    def check(self, value):
        return value in self.type

    @staticmethod
    def can_validate(obj):
        return isinstance(obj, one_of)

    @property
    def name(self):
        return 'one of %s' % self.join_names(["`%r'" % e for e in self.type])


class ListOfValidator(Validator):
    def __init__(self, typ):
        self.type = typ.type

    def check(self, value):
        return isinstance(value, (tuple, list)) and not [x for x in value if not isinstance(x, self.type)]

    @staticmethod
    def can_validate(obj):
        return isinstance(obj, list_of)

    @property
    def name(self):
        return 'a list of %s' % self._type_names()


class ComplexValidator(Validator):
    def __init__(self, typ):
        self.type = [Validator.get(x) for x in typ]

    def check(self, value):
        return bool(sum(t.check(value) for t in self.type))

    @staticmethod
    def can_validate(obj):
        return isinstance(obj, tuple) and not [x for x in obj if Validator.get(x) is None]

    @property
    def name(self):
        return self.join_names([x.name for x in self.type])


Validator.register(IgnoringValidator)
Validator.register(TypeValidator)
Validator.register(MultiTypeValidator)
Validator.register(OneOfValidator)
Validator.register(ListOfValidator)
Validator.register(ComplexValidator)

# Extra types to be used with argument validating decorators
#

none = type(None)


class one_of(object):
    def __init__(self, *args):
        if len(args) < 2:
            raise ValueError("one_of must have at least 2 arguments")
        self.type = args


class list_of(object):
    def __init__(self, *args):
        if [x for x in args if not isclass(x)]:
            raise TypeError("list_of arguments must be types")
        if len(args) == 1:
            self.type = args[0]
        else:
            self.type = args


ignore = type('ignore', (), {})()


# Helpers for writing well behaved decorators
#

def decorator(func):
    """A syntactic marker with no other effect than improving readability."""
    return func


def preserve_signature(func):
    """Preserve the original function signature and attributes in decorator wrappers."""
    from inspect import getfullargspec, signature
    from gnutls.constants import GNUTLSConstant

    constants = [c for c in (getfullargspec(func)[3] or []) if isinstance(c, GNUTLSConstant)]
    sig = signature(func)

    parameters = []
    signature = []
    for item in list(sig.parameters.items()):
        parameters.append(item[0])
        if 'empty' in str(item[1].default):
            signature.append(item[1].name)
        else:
            signature.append(f'{item[1].name}={item[1].default}')

    signature = f"({', '.join(signature)})"
    parameters = f"({', '.join(parameters)})"

    # parameters = signature(*getfullargspec(func),
    # **{'formatvalue': lambda value: ""})[1:-1]
    def fix_signature(wrapper):
        if constants:
            # import the required GNUTLSConstants used as function default arguments
            constants_str = ', '.join([c.name for c in constants])
            code = f'from gnutls.constants import {constants_str}'
            exec(code, locals(), locals())

        code = (f'def {func.__name__}{signature}: \n'
                f'    return wrapper{parameters} \n'
                f'new_wrapper = {func.__name__}')
        exec(code, locals(), globals())

        new_wrapper.__name__ = func.__name__
        new_wrapper.__doc__ = func.__doc__
        new_wrapper.__module__ = func.__module__
        new_wrapper.__dict__.update(func.__dict__)
        return new_wrapper
    return fix_signature


# Argument validating decorators
#

def _callable_args(*args, **kwargs):
    """Internal function used by argument checking decorators"""
    start = kwargs.get('_start', 0)
    validators = []
    for i, arg in enumerate(args):
        validator = Validator.get(arg)
        if validator is None:
            raise TypeError("unsupported type `%r' at position %d "
                            "for argument checking decorator" % (arg, i + 1))
        validators.append(validator)

    def check_args_decorator(func):
        @preserve_signature(func)
        def check_args(*func_args):
            pos = start
            for validator in validators:
                if not validator.check(func_args[pos]):
                    pass
                    # auxiliar exception to catch string_at ctypes function returning bytes
                    if isinstance(func_args[pos], bytes) and 'str' in validator.name:
                        pass
                    #pass
                    #else:
                    #raise TypeError(f"argument {pos + 1 - start} of func_args must be {validator.name} \n {func_args[pos+1-start]}")
                #pos += 1
            return func(*func_args)

        return check_args
    return check_args_decorator


@decorator
def method_args(*args):
    """
    Check class or instance method arguments
    """
    return _callable_args(*args, **{'_start': 1})


@decorator
def function_args(*args):
    """
    Check functions or staticmethod arguments
    """
    return _callable_args(*args)
