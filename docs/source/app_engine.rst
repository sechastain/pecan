.. _app_engine:

App Engine Support
=========================

Pecan runs smoothly in Google's App Engine. There is **no** hacking/patching or weird 
changes that you need to make to work with Pecan. However, since App Engine has certain 
restrictions you may want to be aware of how to set it up correctly.

.. note::
    We do not discuss here how to get an App Engine environment here, nor App Engine 
    specifics that are not related to Pecan. For more info on App Engine go to 
    `their docs <http://code.google.com/appengine/docs/whatisgoogleappengine.html>`_


Dependencies
---------------
Pecan has a few dependencies and one of them is already supported by App Engine (WebOb)
so no need to grab that. Just so you are aware, this is the list of things that you absolutely need 
to grab:

 *  simplegeneric == 0.7
 *  Paste == 1.7.5.1

These are optional, depending on the templating engine you want to use. However, depending on your choice,
you might want to check the engine's dependencies as well. The only engine from this list that doesn't require 
a dependency is Kajiki.

 *  Genshi == 0.6
 *  Kajiki == 0.3.1
 *  Mako == 0.3
 
From this point forward, we will assume you are getting Kajiki, to avoid describing third party dependencies.


Creating the project
----------------------------
Create a directory called ``pecan_gae`` and ``cd`` into it so we can start adding files. We go step by 
step into what needs to go there to get everything running properly.

app.yaml
------------

To start off, you will need your ``app.yaml`` file set properly to map to Pecan. This is how that file should look
like::

    application: foo-bar
    version: 1
    runtime: python
    api_version: 1

    handlers:

    - url: /.*
      script: main.py

Remember the application name will have to match your registered app name in App Engine. The file above maps 
everything to a ``main.py`` file.

This file will be the *root* of our project and will handle everything. 

main.py 
------------
You can name this anything you want, but for consistency we are going with main.py. This file will handle 
all the incoming requests including static files for our Pecan application. This is how it should look::

    from google.appengine.ext.webapp import util
    import sys
    if './lib' not in sys.path:
        sys.path.append('./lib')

    from pecan import Pecan, expose


    class RootController(object):

        @expose('kajiki:index.html')
        def index(self):
            return dict(name="Joe Wu Zap")


    def main():
        application = Pecan(RootController(), template_path='templates')
        util.run_wsgi_app(application)


    if __name__ == '__main__':
        main()

We are doing a few things here... first we are importing the ``util`` module from App Engine that will 
run our Pecan app, then we are importing ``sys`` because we need to add ``lib`` to our path.

The ``lib`` directory is where all our dependencies (including Pecan) will live, so we need to make sure
App Engine will see that as well as all our libraries within ``lib`` (it would not be enough to add a ``__init__.py``
file there.

templates
-----------
The templates directory is where we will have all of our html templates for Pecan. If you don't have it already, go ahead 
and create it and add this html file to it and name it index.html::

    <html>

    <head>
      <title>Hello, ${name}!</title>  
    </head>

    <body>
      <h1>Hello, ${name}!</h1>
    </body>

    </html>

lib
-----
The ``lib`` directory should contain the source for all the dependencies we need. For our example, it should
contain 3 libraries:

 * kajiki
 * paste 
 * pecan 

That is all you need to get this project started!

.. note::
    When grabing the source of the dependencies we mention, make sure you are actually grabing the module itself 
    and not adding the top directory source (where setup.py lives)

Layout
---------
This is how your layout (only showing directories) should look like::

    pecan_gae
    |____app.yaml
    |____lib
    | |____kajiki
    | | |____tests
    | |   |____data
    | |____paste
    | | |____auth
    | | |____cowbell
    | | |____debug
    | | |____evalexception
    | | | |____media
    | | |____exceptions
    | | |____util
    | |____pecan
    |____templates


Trying it out
-------------------------
Now everything should be ready to start serving, so go ahead and run the development server::

    $ ./dev_appserver.py pecan_gae 
    INFO     2010-10-10 12:44:29,476 dev_appserver_main.py:431] Running application pecan-gae on port 8080: http://localhost:8080
    

If you go to your browser and hit ``localhost:8080`` you should see something like this::

        Hello, Joe Wu Zap!

This is the most basic example for App Engine, you can start adding more controllers to handle a bigger 
application and connect everything together. 