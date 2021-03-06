from formencode import Schema, validators
from paste.recursive import ForwardRequestException
from paste.translogger import TransLogger
from unittest import TestCase
from webtest import TestApp

from pecan import Pecan, expose, request, response, redirect, abort, make_app, override_template, render
from pecan.templating import _builtin_renderers as builtin_renderers, error_formatters
from pecan.decorators import accept_noncanonical

import os


class TestBase(TestCase):
    
    def test_simple_app(self):    
        class RootController(object):
            @expose()
            def index(self):
                return 'Hello, World!'
        
        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'
        
        r = app.get('/index')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'
        
        r = app.get('/index.html')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'
    
    def test_object_dispatch(self):
        class SubSubController(object):
            @expose()
            def index(self):
                return '/sub/sub/'
            
            @expose()
            def deeper(self):
                return '/sub/sub/deeper'
        
        class SubController(object):
            @expose()
            def index(self):
                return '/sub/'
                
            @expose()
            def deeper(self):
                return '/sub/deeper'
                
            sub = SubSubController()
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
            
            @expose()
            def deeper(self):
                return '/deeper'
            
            sub = SubController()
        
        app = TestApp(Pecan(RootController()))
        for path in ('/', '/deeper', '/sub/', '/sub/deeper', '/sub/sub/', '/sub/sub/deeper'):
            r = app.get(path)
            assert r.status_int == 200
            assert r.body == path
    
    def test_lookup(self):
        class LookupController(object):
            def __init__(self, someID):
                self.someID = someID
            
            @expose()
            def index(self):
                return '/%s' % self.someID
            
            @expose()
            def name(self):
                return '/%s/name' % self.someID
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
            
            @expose()
            def _lookup(self, someID, *remainder):
                return LookupController(someID), remainder
        
        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == '/'
        
        r = app.get('/100/')
        assert r.status_int == 200
        assert r.body == '/100'
        
        r = app.get('/100/name')
        assert r.status_int == 200
        assert r.body == '/100/name'

    def test_lookup_with_wrong_argspec(self):
        class RootController(object):
            @expose()
            def _lookup(self, someID):
                return 'Bad arg spec'

        app = TestApp(Pecan(RootController()))
        r = app.get('/foo/bar', expect_errors=True)
        r.status_int == 404

    def test_controller_args(self):
        class RootController(object):
            @expose()
            def index(self, id):
                return 'index: %s' % id
            
            @expose()
            def multiple(self, one, two):
                return 'multiple: %s, %s' % (one, two)
            
            @expose()
            def optional(self, id=None):
                return 'optional: %s' % str(id)
            
            @expose()
            def multiple_optional(self, one=None, two=None, three=None):
                return 'multiple_optional: %s, %s, %s' % (one, two, three)
            
            @expose()
            def variable_args(self, *args):
                return 'variable_args: %s' % ', '.join(args)
            
            @expose()
            def variable_kwargs(self, **kwargs):
                data = ['%s=%s' % (key, kwargs[key]) for key in sorted(kwargs.keys())]
                return 'variable_kwargs: %s' % ', '.join(data)
            
            @expose()
            def variable_all(self, *args, **kwargs):
                data = ['%s=%s' % (key, kwargs[key]) for key in sorted(kwargs.keys())]
                return 'variable_all: %s' % ', '.join(list(args) + data)
            
            @expose()
            def eater(self, id, dummy=None, *args, **kwargs):
                data = ['%s=%s' % (key, kwargs[key]) for key in sorted(kwargs.keys())]
                return 'eater: %s, %s, %s' % (id, dummy, ', '.join(list(args) + data))
            
            @expose()
            def _route(self, args):
                if hasattr(self, args[0]):
                    return getattr(self, args[0]), args[1:]
                else:
                    return self.index, args
        
        app = TestApp(Pecan(RootController()))
        
        # required arg
        
        try:
            r = app.get('/')
            assert r.status_int != 200
        except Exception, ex:
            assert type(ex) == TypeError
            assert ex.args[0] == 'index() takes exactly 2 arguments (1 given)'
        
        r = app.get('/1')
        assert r.status_int == 200
        assert r.body == 'index: 1'

        r = app.get('/This%20is%20a%20test%21')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'
        
        r = app.get('/1/dummy', status=404)
        assert r.status_int == 404
        
        r = app.get('/?id=2')
        assert r.status_int == 200
        assert r.body == 'index: 2'

        r = app.get('/?id=This%20is%20a%20test%21')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'
        
        r = app.get('/3?id=three')
        assert r.status_int == 200
        assert r.body == 'index: 3'

        r = app.get('/This%20is%20a%20test%21?id=three')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'
        
        r = app.post('/', {'id': '4'})
        assert r.status_int == 200
        assert r.body == 'index: 4'
        
        r = app.post('/4', {'id': 'four'})
        assert r.status_int == 200
        assert r.body == 'index: 4'
        
        r = app.get('/?id=5&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'index: 5'
        
        r = app.post('/', {'id': '6', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'index: 6'
        
        # multiple args
        
        r = app.get('/multiple/one/two')
        assert r.status_int == 200
        assert r.body == 'multiple: one, two'

        r = app.get('/multiple/One%20/Two%21')
        assert r.status_int == 200
        assert r.body == 'multiple: One , Two!'
        
        r = app.get('/multiple?one=three&two=four')
        assert r.status_int == 200
        assert r.body == 'multiple: three, four'

        r = app.get('/multiple?one=Three%20&two=Four%20%21')
        assert r.status_int == 200
        assert r.body == 'multiple: Three , Four !'
        
        r = app.post('/multiple', {'one': 'five', 'two': 'six'})
        assert r.status_int == 200
        assert r.body == 'multiple: five, six'

        r = app.post('/multiple', {'one': 'Five%20', 'two': 'Six%20%21'})
        assert r.status_int == 200
        assert r.body == 'multiple: Five%20, Six%20%21'
        
        # optional arg
        
        r = app.get('/optional')
        assert r.status_int == 200
        assert r.body == 'optional: None'
        
        r = app.get('/optional/1')
        assert r.status_int == 200
        assert r.body == 'optional: 1'

        r = app.get('/optional/Some%20Number')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'
        
        r = app.get('/optional/2/dummy', status=404)
        assert r.status_int == 404
        
        r = app.get('/optional?id=2')
        assert r.status_int == 200
        assert r.body == 'optional: 2'

        r = app.get('/optional?id=Some%20Number')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'
        
        r = app.get('/optional/3?id=three')
        assert r.status_int == 200
        assert r.body == 'optional: 3'

        r = app.get('/optional/Some%20Number?id=three')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'
        
        r = app.post('/optional', {'id': '4'})
        assert r.status_int == 200
        assert r.body == 'optional: 4'

        r = app.post('/optional', {'id': 'Some%20Number'})
        assert r.status_int == 200
        assert r.body == 'optional: Some%20Number'
        
        r = app.post('/optional/5', {'id': 'five'})
        assert r.status_int == 200
        assert r.body == 'optional: 5'

        r = app.post('/optional/Some%20Number', {'id': 'five'})
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'
        
        r = app.get('/optional?id=6&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'optional: 6'

        r = app.get('/optional?id=Some%20Number&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'
        
        r = app.post('/optional', {'id': '7', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'optional: 7'

        r = app.post('/optional', {'id': 'Some%20Number', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'optional: Some%20Number'
        
        # multiple optional args
        
        r = app.get('/multiple_optional')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, None'
        
        r = app.get('/multiple_optional/1')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

        r = app.get('/multiple_optional/One%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'
        
        r = app.get('/multiple_optional/1/2/3')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

        r = app.get('/multiple_optional/One%21/Two%21/Three%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, Two!, Three!'
        
        r = app.get('/multiple_optional/1/2/3/dummy', status=404)
        assert r.status_int == 404
        
        r = app.get('/multiple_optional?one=1')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

        r = app.get('/multiple_optional?one=One%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'
        
        r = app.get('/multiple_optional/1?one=one')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

        r = app.get('/multiple_optional/One%21?one=one')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'
        
        r = app.post('/multiple_optional', {'one': '1'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

        r = app.post('/multiple_optional', {'one': 'One%21'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One%21, None, None'
        
        r = app.post('/multiple_optional/1', {'one': 'one'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

        r = app.post('/multiple_optional/One%21', {'one': 'one'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'
        
        r = app.get('/multiple_optional?one=1&two=2&three=3&four=4')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

        r = app.get('/multiple_optional?one=One%21&two=Two%21&three=Three%21&four=4')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, Two!, Three!'
        
        r = app.post('/multiple_optional', {'one': '1', 'two': '2', 'three': '3', 'four': '4'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

        r = app.post('/multiple_optional', {'one': 'One%21', 'two': 'Two%21', 'three': 'Three%21', 'four': '4'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One%21, Two%21, Three%21'
        
        r = app.get('/multiple_optional?three=3')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, 3'

        r = app.get('/multiple_optional?three=Three%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, Three!'
        
        r = app.get('/multiple_optional', {'two': '2'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, 2, None'
        
        # variable args
        
        r = app.get('/variable_args')
        assert r.status_int == 200
        assert r.body == 'variable_args: '
        
        r = app.get('/variable_args/1/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_args: 1, dummy'

        r = app.get('/variable_args/Testing%20One%20Two/Three%21')
        assert r.status_int == 200
        assert r.body == 'variable_args: Testing One Two, Three!'
        
        r = app.get('/variable_args?id=2&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'variable_args: '
        
        r = app.post('/variable_args', {'id': '3', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'variable_args: '
        
        # variable keyword args
        
        r = app.get('/variable_kwargs')
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: '
        
        r = app.get('/variable_kwargs/1/dummy', status=404)
        assert r.status_int == 404
        
        r = app.get('/variable_kwargs?id=2&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=dummy, id=2'

        r = app.get('/variable_kwargs?id=Two%21&dummy=This%20is%20a%20test')
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=This is a test, id=Two!'
        
        r = app.post('/variable_kwargs', {'id': '3', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=dummy, id=3'

        r = app.post('/variable_kwargs', {'id': 'Three%21', 'dummy': 'This%20is%20a%20test'})
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=This%20is%20a%20test, id=Three%21'
        
        # variable args & keyword args
        
        r = app.get('/variable_all')
        assert r.status_int == 200
        assert r.body == 'variable_all: '
        
        r = app.get('/variable_all/1')
        assert r.status_int == 200
        assert r.body == 'variable_all: 1'
        
        r = app.get('/variable_all/2/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_all: 2, dummy'
        
        r = app.get('/variable_all/3?month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'variable_all: 3, day=12, month=1'
        
        r = app.get('/variable_all/4?id=four&month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'variable_all: 4, day=12, id=four, month=1'
        
        r = app.post('/variable_all/5/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_all: 5, dummy'
        
        r = app.post('/variable_all/6', {'month': '1', 'day': '12'})
        assert r.status_int == 200
        assert r.body == 'variable_all: 6, day=12, month=1'
        
        r = app.post('/variable_all/7', {'id': 'seven', 'month': '1', 'day': '12'})
        assert r.status_int == 200
        assert r.body == 'variable_all: 7, day=12, id=seven, month=1'
        
        # the "everything" controller
        
        try:
            r = app.get('/eater')
            assert r.status_int != 200
        except Exception, ex:
            assert type(ex) == TypeError
            assert ex.args[0] == 'eater() takes at least 2 arguments (1 given)'
        
        r = app.get('/eater/1')
        assert r.status_int == 200
        assert r.body == 'eater: 1, None, '
        
        r = app.get('/eater/2/dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 2, dummy, '
        
        r = app.get('/eater/3/dummy/foo/bar')
        assert r.status_int == 200
        assert r.body == 'eater: 3, dummy, foo, bar'
        
        r = app.get('/eater/4?month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'eater: 4, None, day=12, month=1'
        
        r = app.get('/eater/5?id=five&month=1&day=12&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 5, dummy, day=12, month=1'
        
        r = app.post('/eater/6')
        assert r.status_int == 200
        assert r.body == 'eater: 6, None, '
        
        r = app.post('/eater/7/dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 7, dummy, '
        
        r = app.post('/eater/8/dummy/foo/bar')
        assert r.status_int == 200
        assert r.body == 'eater: 8, dummy, foo, bar'
        
        r = app.post('/eater/9', {'month': '1', 'day': '12'})
        assert r.status_int == 200
        assert r.body == 'eater: 9, None, day=12, month=1'
        
        r = app.post('/eater/10', {'id': 'ten', 'month': '1', 'day': '12', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'eater: 10, dummy, day=12, month=1'
        
    def test_abort(self):
        class RootController(object):
            @expose()
            def index(self):
                abort(404)
        
        app = TestApp(Pecan(RootController()))
        r = app.get('/', status=404)
        assert r.status_int == 404
    
    def test_redirect(self):
        class RootController(object):
            @expose()
            def index(self):
                redirect('/testing')
            
            @expose()
            def internal(self):
                redirect('/testing', internal=True)
            
            @expose()
            def bad_internal(self):
                redirect('/testing', internal=True, code=301)
            
            @expose()
            def permanent(self):
                redirect('/testing', code=301)
            
            @expose()
            def testing(self):
                return 'it worked!'
        
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 302
        r = r.follow()
        assert r.status_int == 200
        assert r.body == 'it worked!'
        
        r = app.get('/internal')
        assert r.status_int == 200
        assert r.body == 'it worked!'
        
        self.assertRaises(ValueError, app.get, '/bad_internal')
        
        r = app.get('/permanent')
        assert r.status_int == 301
        r = r.follow()
        assert r.status_int == 200
        assert r.body == 'it worked!'
        
    def test_streaming_response(self):
        import StringIO
        class RootController(object):
            @expose(content_type='text/plain')
            def test(self, foo):
                if foo == 'stream':
                    # mimic large file
                    contents = StringIO.StringIO('stream')
                    response.content_type='application/octet-stream'
                    contents.seek(0, os.SEEK_END)
                    response.content_length = contents.tell()
                    contents.seek(0, os.SEEK_SET)
                    response.app_iter = contents
                    return response
                else:
                    return 'plain text'

        app = TestApp(Pecan(RootController()))
        r = app.get('/test/stream')
        assert r.content_type == 'application/octet-stream'
        assert r.body == 'stream'

        r = app.get('/test/plain')
        assert r.content_type == 'text/plain'
        assert r.body == 'plain text'
    
    def test_request_state_cleanup(self):
        """
        After a request, the state local() should be totally clean
        except for state.app (so that objects don't leak between requests)
        """
        from pecan.core import state
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == '/'
        
        assert state.__dict__.keys() == ['app']

    def test_extension(self):
        """
        Test extension splits
        """
        class RootController(object):
            @expose(content_type=None)
            def _default(self, *args):
                from pecan.core import request
                return request.pecan['extension']

        app = TestApp(Pecan(RootController()))
        r = app.get('/index.html')
        assert r.status_int == 200
        assert r.body == '.html'

        r = app.get('/image.png')
        assert r.status_int == 200
        assert r.body == '.png'

        r = app.get('/.vimrc')
        assert r.status_int == 200
        assert r.body == ''

        r = app.get('/gradient.js.js')
        assert r.status_int == 200
        assert r.body == '.js'

    def test_app_wrap(self):
        class RootController(object):
            pass

        wrapped_apps = []
        def wrap(app):
            wrapped_apps.append(app)
            return app

        app = make_app(RootController(), wrap_app=wrap, debug=True)
        assert len(wrapped_apps) == 1
    
    def test_bad_content_type(self):
        class RootController(object):
            @expose()
            def index(self):
                return '/'
    
        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == '/'
        
        r = app.get('/index.html', expect_errors=True)
        assert r.status_int == 200
        assert r.body == '/'

        r = app.get('/index.txt', expect_errors=True)
        assert r.status_int == 404

    def test_canonical_index(self):
        class ArgSubController(object):
            @expose()
            def index(self, arg):
                return arg
        class AcceptController(object):
            @accept_noncanonical
            @expose()
            def index(self):
                return 'accept'
        class SubController(object):
            @expose()
            def index(self):
                return 'subindex'
        class RootController(object):
            @expose()
            def index(self):
                return 'index'

            sub = SubController()
            arg = ArgSubController()
            accept = AcceptController()

        app = TestApp(Pecan(RootController()))

        r = app.get('/')
        assert r.status_int == 200
        assert 'index' in r.body

        r = app.get('/index')
        assert r.status_int == 200
        assert 'index' in r.body
        
        # for broken clients
        r = app.get('', status=302)
        assert r.status_int == 302

        r = app.get('/sub/')
        assert r.status_int == 200
        assert 'subindex' in r.body

        r = app.get('/sub', status=302)
        assert r.status_int == 302

        try:
            r = app.post('/sub', dict(foo=1))
            raise Exception, "Post should fail"
        except Exception, e:
            assert isinstance(e, RuntimeError)

        r = app.get('/arg/index/foo')
        assert r.status_int == 200
        assert r.body == 'foo'

        r = app.get('/accept/')
        assert r.status_int == 200
        assert 'accept' == r.body

        r = app.get('/accept')
        assert r.status_int == 200
        assert 'accept' == r.body

        app = TestApp(Pecan(RootController(), force_canonical=False))
        r = app.get('/')
        assert r.status_int == 200
        assert 'index' in r.body

        r = app.get('/sub')
        assert r.status_int == 200
        assert 'subindex' in r.body

        r = app.post('/sub', dict(foo=1))
        assert r.status_int == 200
        assert 'subindex' in r.body

        r = app.get('/sub/')
        assert r.status_int == 200
        assert 'subindex' in r.body
    
    def test_proxy(self):
        class RootController(object):
            @expose()
            def index(self):
                request.testing = True
                assert request.testing == True
                del request.testing
                assert hasattr(request, 'testing') == False
                return '/'
        
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200


class TestLogging(TestCase):
    """
    Mocks logging calls so we can make sure they get called. We could use 
    Fudge for this, but it would add an additional dependency to Pecan for 
    a single set of tests.
    """
    
    def setUp(self):
        self._write_log = TransLogger.write_log
    
    def tearDown(self):
        TransLogger.write_log = self._write_log
    
    def test_default(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # monkeypatch the logger
        writes = []
        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200
        assert writes == []
    
    def test_default(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # monkeypatch the logger
        writes = []
        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 0
    
    def test_no_logging(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # monkeypatch the logger
        writes = []
        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging=False))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 0
    
    def test_basic_logging(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # monkeypatch the logger
        writes = []
        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging=True))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1
    
    def test_empty_config(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # monkeypatch the logger
        writes = []
        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging={}))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1
    
    def test_custom_config(self):
        
        class RootController(object):
            @expose()
            def index(self):
                return '/'
        
        # create a custom logger
        writes = []
        class FakeLogger(object):
            def log(self, *args, **kwargs):
                writes.append(1)
        
        # check the request
        app = TestApp(make_app(RootController(), debug=True, 
                               logging={'logger': FakeLogger()}))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1


class TestEngines(object):
    
    template_path = os.path.join(os.path.dirname(__file__), 'templates')

    def test_genshi(self):
        if 'genshi' not in builtin_renderers:
            return

        class RootController(object):
            @expose('genshi:genshi.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('genshi:genshi_bad.html')
            def badtemplate(self):
                return dict()
        
        app = TestApp(Pecan(RootController(), template_path=self.template_path))    
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body
        
        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body
 
        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None
    
    def test_kajiki(self):
        if 'kajiki' not in builtin_renderers:
            return

        class RootController(object):
            @expose('kajiki:kajiki.html')
            def index(self, name='Jonathan'):
                return dict(name=name)
        
        app = TestApp(Pecan(RootController(), template_path=self.template_path))
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body
        
        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body

    def test_jinja(self):
        if 'jinja' not in builtin_renderers:
            return
        class RootController(object):
            @expose('jinja:jinja.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('jinja:jinja_bad.html')
            def badtemplate(self):
                return dict()

        app = TestApp(Pecan(RootController(), template_path=self.template_path))
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body

        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None
   
    def test_mako(self):
        if 'mako' not in builtin_renderers:
            return
        class RootController(object):
            @expose('mako:mako.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('mako:mako_bad.html')
            def badtemplate(self):
                return dict()
        
        app = TestApp(Pecan(RootController(), template_path=self.template_path))
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body
        
        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body
        
        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None
    
    def test_json(self):
        try:
            from simplejson import loads
        except:
            from json import loads
        
        expected_result = dict(name='Jonathan', age=30, nested=dict(works=True))
        
        class RootController(object):
            @expose('json')
            def index(self):
                return expected_result
        
        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        result = dict(loads(r.body))
        assert result == expected_result

    def test_override_template(self):
        class RootController(object):
            @expose('foo.html')
            def index(self):
                override_template(None, content_type='text/plain')
                return 'Override'

        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert 'Override' in r.body 
        assert r.content_type == 'text/plain'

    def test_render(self):
        
        #if 'mako' not in builtin_renderers:
        #    return
        
        class RootController(object):
            @expose()
            def index(self, name='Jonathan'):
                return render('mako.html', dict(name=name))
                return dict(name=name)
        
        app = TestApp(Pecan(RootController(), template_path=self.template_path))
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body
