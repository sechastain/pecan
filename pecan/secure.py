from inspect import getmembers, ismethod, isfunction
from webob import exc

from decorators import expose
from util import _cfg, iscontroller

__all__ = ['unlocked', 'secure', 'SecureController']

class _SecureState(object):
    def __init__(self, desc, boolean_value):
        self.description = desc
        self.boolean_value = boolean_value
    def __repr__(self):
        return '<SecureState %s>' % self.description
    def __nonzero__(self):
        return self.boolean_value

Any = _SecureState('Any', False)
Protected = _SecureState('Protected', True)

# security method decorators 
def _unlocked_method(func):
    _cfg(func)['secured'] = Any
    return func

def _secure_method(check_permissions_func):
    def wrap(func):
        cfg = _cfg(func)
        cfg['secured'] = Protected
        cfg['check_permissions'] = check_permissions_func
        return func
    return wrap

# classes to assist with wrapping attributes
class _UnlockedAttribute(object):
    def __init__(self, obj):
        self.obj = obj

    @_unlocked_method
    @expose()
    def _lookup(self, *remainder):
        return self.obj, remainder

class _SecuredAttribute(object):
    def __init__(self, obj, check_permissions):
        self.obj = obj
        self.check_permissions = check_permissions
        self._parent = None

    def _check_permissions(self):
        if isinstance(self.check_permissions, basestring):
            return getattr(self.parent, self.check_permissions)()
        else:
            return self.check_permissions()

    def __get_parent(self):
        return self._parent
    def __set_parent(self, parent):
        if ismethod(parent):
            self._parent = parent.im_self
        else:
            self._parent = parent
    parent = property(__get_parent, __set_parent)

    @_secure_method('_check_permissions')
    @expose()
    def _lookup(self, *remainder):
        return self.obj, remainder

# helper for secure decorator
def _allowed_check_permissions_types(x):
    return (ismethod(x) or 
            isfunction(x) or 
            isinstance(x, basestring)
        )

# methods that can either decorate functions or wrap classes
# these should be the main methods used for securing or unlocking
def unlocked(func_or_obj):
    """
    This method unlocks method or class attribute on a SecureController.  Can
    be used to decorate or wrap an attribute
    """
    if ismethod(func_or_obj) or isfunction(func_or_obj):
        return _unlocked_method(func_or_obj)
    else:
        return _UnlockedAttribute(func_or_obj)


def secure(func_or_obj, check_permissions_for_obj=None):
    """
    This method secures a method or class depending on invocation.

    To decorate a method use one argument:
        @secure(<check_permissions_method>)

    To secure a class, invoke with two arguments:
        secure(<obj instance>, <check_permissions_method>)
    """

    if _allowed_check_permissions_types(func_or_obj):
        return _secure_method(func_or_obj)
    else:
        if not _allowed_check_permissions_types(check_permissions_for_obj):
            raise TypeError, "When securing an object, secure() requires the second argument to be method"
        return _SecuredAttribute(func_or_obj, check_permissions_for_obj)


class SecureController(object):
    """
    Used to apply security to a controller. 
    Implementations of SecureController should extend the
    `check_permissions` method to return a True or False
    value (depending on whether or not the user has permissions
    to the controller).
    """
    class __metaclass__(type):
        def __init__(cls, name, bases, dict_):
            cls._pecan = dict(secured=Protected, check_permissions=cls.check_permissions, unlocked=[])

            for name, value in getmembers(cls):
                if ismethod(value):
                    if iscontroller(value) and value._pecan.get('secured') is None:
                        value._pecan['secured'] = Protected
                        value._pecan['check_permissions'] = cls.check_permissions
                elif hasattr(value, '__class__'):
                    if name.startswith('__') and name.endswith('__'): continue
                    if isinstance(value, _UnlockedAttribute):
                        # mark it as unlocked and remove wrapper
                        cls._pecan['unlocked'].append(value.obj)
                        setattr(cls, name, value.obj)
                    elif isinstance(value, _SecuredAttribute):
                        # The user has specified a different check_permissions
                        # than the class level version.  As far as the class
                        # is concerned, this method is unlocked because 
                        # it is using a check_permissions function embedded in
                        # the _SecuredAttribute wrapper
                        cls._pecan['unlocked'].append(value)

    @classmethod
    def check_permissions(cls):
        return False

# methods to evaluate security during routing
def handle_security(controller):
    """ Checks the security of a controller.  """
    if controller._pecan.get('secured', False):
        check_permissions = controller._pecan['check_permissions']

        if isinstance(check_permissions, basestring):
            check_permissions = getattr(controller.im_self, check_permissions)

        if not check_permissions():
            raise exc.HTTPUnauthorized

def cross_boundary(prev_obj, obj):
    """ Check permissions as we move between object instances. """
    if prev_obj is None:
        return

    if isinstance(obj, _SecuredAttribute):
        # a secure attribute can live in unsecure class so we have to set
        # while we walk the route
        obj.parent = prev_obj

    if hasattr(prev_obj, '_pecan'):
        if obj not in prev_obj._pecan.get('unlocked', []):
            handle_security(prev_obj)
