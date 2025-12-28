import typing

import cachelib

import flask

import flask_phpbb3.backends.base
import flask_phpbb3.sessions


class PhpBB3:
    def __init__(
        self,
        app: typing.Optional[flask.Flask] = None,
        cache: typing.Optional[cachelib.BaseCache] = None,
    ) -> None:
        self.app = app
        if app is not None:
            self.init_app(app, cache)

    def init_app(
        self,
        app: flask.Flask,
        cache: typing.Optional[cachelib.BaseCache] = None
    ) -> None:
        self._ensure_default_config(app)

        # Use passed in cache interface (see Flask-Cache extension)
        cache_driver: cachelib.BaseCache
        if not cache:
            # Setup our own
            cache_backend = app.config['PHPBB3_SESSION_BACKEND']['TYPE']
            if cache_backend == 'memcached':
                key_prefix = app.config['PHPBB3_SESSION_BACKEND']['KEY_PREFIX']
                cache_driver = cachelib.MemcachedCache(
                    app.config['PHPBB3_SESSION_BACKEND']['SERVERS'],
                    key_prefix=key_prefix,
                )
            else:
                cache_driver = cachelib.SimpleCache()
        else:
            cache_driver = cache

        # Setup teardown
        app.teardown_appcontext(self.teardown)

        # Add ourselves to the app, so session interface can function
        setattr(app, 'phpbb3', self)
        setattr(app, 'phpbb3_cache', cache_driver)

        # Use our session interface
        # TODO Is it wise to do it here? Should user do it himself?
        app.session_interface =\
            flask_phpbb3.sessions.PhpBB3SessionInterface()

    @classmethod
    def _ensure_default_config(cls, app: flask.Flask) -> None:
        app.config.setdefault('PHPBB3', {})
        app.config['PHPBB3'].setdefault('DRIVER', 'psycopg2')
        app.config['PHPBB3'].setdefault('VERSION', '3.1')
        app.config.setdefault('PHPBB3_DATABASE', {})
        app.config['PHPBB3_DATABASE'].setdefault('HOST', '127.0.0.1')
        app.config['PHPBB3_DATABASE'].setdefault('DATABASE', 'phpbb3')
        app.config['PHPBB3_DATABASE'].setdefault('USER', 'phpbb3')
        app.config['PHPBB3_DATABASE'].setdefault('PASSWORD', '')
        app.config['PHPBB3_DATABASE'].setdefault('TABLE_PREFIX', 'phpbb_')
        app.config['PHPBB3_DATABASE'].setdefault('CUSTOM_USER_FIELDS', [])
        app.config['PHPBB3_DATABASE'].setdefault('CUSTOM_STATEMENTS', {})
        app.config.setdefault('PHPBB3_SESSION_BACKEND', {})
        app.config['PHPBB3_SESSION_BACKEND'].setdefault('TYPE', 'simple')
        app.config.setdefault('PHPBB3_BOTLIST', [])

        # Conditional defaults
        if app.config['PHPBB3_SESSION_BACKEND']['TYPE'] == 'memcached':
            app.config['PHPBB3_SESSION_BACKEND'].setdefault(
                'KEY_PREFIX',
                'phpbb3'
            )
            app.config['PHPBB3_SESSION_BACKEND'].setdefault(
                'SERVERS',
                ['127.0.0.1:11211']
            )

    @classmethod
    def _create_backend(
        cls,
        backend_type: str,
        config: typing.Dict[str, typing.Any],
        cache: cachelib.BaseCache
    ) -> flask_phpbb3.backends.base.BaseBackend:
        if backend_type == 'psycopg2':
            import flask_phpbb3.backends.psycopg2
            return flask_phpbb3.backends.psycopg2.Psycopg2Backend(
                cache,
                config,
            )
        else:
            raise ValueError('Unsupported driver {}'.format(backend_type))

    @property
    def _backend(self) -> flask_phpbb3.backends.base.BaseBackend:
        """Returns phpbb3 backend"""
        current_app = self.app or flask.current_app

        backend: typing.Optional[flask_phpbb3.backends.base.BaseBackend] =\
            flask.g.get('phpbb3_backend', None)

        if backend is None or backend.is_closed:
            if not hasattr(current_app, 'phpbb3_cache'):
                raise ValueError(
                    'App not properly configured, phpbb3_cache is missing!'
                )

            cache = getattr(current_app, 'phpbb3_cache')
            backend = PhpBB3._create_backend(
                current_app.config['PHPBB3']['DRIVER'],
                current_app.config['PHPBB3_DATABASE'],
                cache,
            )
            flask.g.setdefault('phpbb3_backend', backend)
        return backend

    def get_autologin(
        self,
        key: str,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None
    ) -> typing.Optional[typing.Dict]:
        output: typing.Optional[typing.Dict] = self._backend.execute(
            'get_autologin',
            key=key,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def get_session(
        self,
        session_id: str,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None
    ) -> typing.Optional[typing.Dict]:
        output: typing.Optional[typing.Dict] = self._backend.execute(
            'get_session',
            session_id=session_id,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def get_user(
        self,
        user_id: int,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None
    ) -> typing.Optional[typing.Dict]:
        output: typing.Optional[typing.Dict] = self._backend.execute(
            'get_user',
            user_id=user_id,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def get_user_profile(
        self,
        user_id: int,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None
    ) -> typing.Optional[typing.Dict]:
        output: typing.Optional[typing.Dict] = self._backend.execute(
            'get_user_profile',
            user_id=user_id,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def has_membership(
        self,
        user_id: int,
        group_id: int,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None,
    ) -> typing.Optional[bool]:
        output: typing.Optional[bool] = self._backend.execute(
            'has_membership',
            user_id=user_id,
            group_id=group_id,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def has_membership_resolve(
        self,
        user_id: int,
        group_name: str,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None,
    ) -> typing.Optional[bool]:
        output: typing.Optional[bool] = self._backend.execute(
            'has_membership_resolve',
            user_id=user_id,
            group_name=group_name,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def fetch_acl_options(
        self,
        skip: int = 0,
        limit: typing.Optional[int] = 10,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None,
    ) -> typing.Optional[typing.List[typing.Dict]]:
        output: typing.Optional[typing.List[typing.Dict]] =\
            self._backend.execute(
                'fetch_acl_options',
                skip=skip,
                limit=limit,
                cache=cache,
                cache_ttl=cache_ttl,
            )
        return output

    def get_unread_notifications_count(
        self,
        user_id: int,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None,
    ) -> typing.Optional[typing.Dict]:
        output: typing.Optional[typing.Dict] = self._backend.execute(
            'get_unread_notifications_count',
            user_id=user_id,
            cache=cache,
            cache_ttl=cache_ttl,
        )
        return output

    def get_user_acl(
        self,
        raw_user_permissions: str
    ) -> flask_phpbb3.backends.base.UserAcl:
        return self._backend.get_user_acl(raw_user_permissions)

    def execute_custom(
        self,
        command: str,
        cache: bool = False,
        cache_ttl: typing.Optional[int] = None,
        **kwargs: typing.Any
    ) -> typing.Any:
        output = self._backend.execute(
            command,
            cache=cache,
            cache_ttl=cache_ttl,
            **kwargs
        )
        return output

    def teardown(self, exception: typing.Any) -> None:
        backend: flask_phpbb3.backends.base.BaseBackend =\
            flask.g.get('phpbb3_backend', None)
        if backend is not None:
            backend.close()
