import abc
from typing import Any, Dict, Optional

import cachelib


ACL_OPTIONS_CACHE_TTL: int = 3600 * 1


class BaseBackend:
    KNOWN_OPERATIONS = (
        'fetch',
        'get',
        'has',
        'set',
    )
    KNOWN_DRIVERS = (
        'psycopg2',
    )

    def __init__(
        self,
        cache: cachelib.BaseCache,
        config: Dict[str, Any]
    ):
        self._functions: Dict[str, str] = {}
        self._connection = None
        self._cache = cache
        self._config = config

        self._prepare_statements()
        custom_statements = self._config.get('CUSTOM_STATEMENTS', {})
        if not isinstance(custom_statements, dict):
            custom_statements = {}
        self._functions.update(custom_statements)

    @abc.abstractmethod
    def _setup_connection(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _prepare_statements(self) -> None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _db(self) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def execute(
        self,
        command: str,
        cache: bool = False,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_closed(self) -> bool:
        raise NotImplementedError

    def get_user_acl(self, raw_user_permissions: str) -> UserAcl:
        raw_acl_options = self.execute(
            'fetch_acl_options',
            cache=True,
            cache_ttl=ACL_OPTIONS_CACHE_TTL,
            limit=None,
        )
        return UserAcl(raw_acl_options, raw_user_permissions)


class UserAcl(object):
    def __init__(self, raw_acl_options, raw_user_permissions):
        # type: (typing.List[dict], str) -> None
        self._acl_options = self._parse_acl_options(raw_acl_options)
        self._acl = self._parse_user_permissions(raw_user_permissions)
        self._acl_lookup_cache = {}  # type: dict

    @classmethod
    def _parse_acl_options(cls, raw_acl_options):
        # type: (typing.List[dict]) -> dict
        # Load ACL options, so we can decode the user ACL
        acl_options = {
            'local': {},
            'global': {}
        }  # type: dict
        local_index = 0
        global_index = 0

        for opt in raw_acl_options or []:
            if opt['is_local'] == 1:
                acl_options['local'][opt['auth_option']] =\
                    local_index
                local_index += 1
            if opt['is_global'] == 1:
                acl_options['global'][opt['auth_option']] =\
                    global_index
                global_index += 1
            # TODO By looking phpbb3 code, here also comes translation
            # option <=> id

        return acl_options

    @classmethod
    def _parse_user_permissions(cls, raw_user_permissions):
        # type: (str) -> dict
        seq_cache = {}  # type: dict
        acl = {}

        split_user_permissions = raw_user_permissions\
            .rstrip()\
            .splitlines()
        for forum_id, perms in enumerate(split_user_permissions):
            if not perms:
                continue

            # Do the conversion magic
            acl[str(forum_id)] = ''
            for sub in [perms[j:j + 6] for j in range(0, len(perms), 6)]:
                if sub in seq_cache:
                    converted = seq_cache[sub]
                else:
                    converted = bin(int(sub, 36))[2:]
                    converted = seq_cache[sub] = '0'\
                                                 * (31 - len(converted))\
                                                 + converted

                acl[str(forum_id)] += converted

        return acl

    def has_privilege(self, privilege, forum_id=0):
        # type: (str, int) -> bool
        # Parse negation
        str_forum_id = str(forum_id)

        negated = privilege.startswith('!')
        if negated:
            option = privilege[1:]
        else:
            option = privilege

        self._acl_lookup_cache.setdefault(str_forum_id, {})[option] = False

        # Global permissions
        if option in self._acl_options['global']\
           and '0' in self._acl:
            try:
                acl_option = self._acl_options['global'][option]
                permission = self._acl['0'][acl_option]
                self._acl_lookup_cache[str_forum_id][option] =\
                    bool(int(permission))
            except IndexError:
                pass

        # Local permissions
        if str_forum_id != '0'\
           and option in self._acl_options['local']:
            try:
                acl_option = self._acl_options['local'][option]
                permission =\
                    self._acl.get(str_forum_id, '0' * 31)[acl_option]
                self._acl_lookup_cache[str_forum_id][option] |=\
                    bool(int(permission))
            except IndexError:
                pass

        output = (
            negated ^ self._acl_lookup_cache[str_forum_id][option]
        )  # type: bool
        return output

    def has_privileges(self, *privileges, **kwargs):
        # type: (*str, **int) -> bool
        forum_id = kwargs.get('forum_id', 0)

        output = False
        for option in privileges:
            output |= self.has_privilege(option, forum_id=forum_id)
        return output
