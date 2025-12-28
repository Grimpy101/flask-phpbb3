from unittest import mock

from flask_phpbb3 import PhpBB3

from . import base

setUpModule = base.setUpModule
tearDownModule = base.tearDownModule


class TestExtension(base.TestWithDatabase):
    @mock.patch("flask_phpbb3.backends.psycopg2.Psycopg2Backend.close")
    def test_teardown(self, mocked_close: mock.Mock) -> None:
        self.ctx.pop()
        mocked_close.assert_called()
        self.ctx.push()


class TestGetUser(base.TestWithDatabase):
    def test_anonymous_user(self) -> None:
        phpbb3: PhpBB3 = getattr(self.app, "phpbb3")
        anonymous_user = phpbb3.get_user(user_id=1)

        self.assertIsNotNone(anonymous_user)
        if anonymous_user is not None:
            self.assertEqual(anonymous_user["username"], "Anonymous")
            self.assertEqual(anonymous_user["user_id"], 1)

    def test_user(self) -> None:
        base._create_user(self.cursor)

        phpbb3: PhpBB3 = getattr(self.app, "phpbb3")
        user = phpbb3.get_user(user_id=2)

        self.assertIsNotNone(user)
        if user is not None:
            self.assertEqual(user["username"], "test")
            self.assertEqual(user["user_id"], 2)

    def test_unknown_user(self) -> None:
        phpbb3: PhpBB3 = getattr(self.app, "phpbb3")
        unknown_user = phpbb3.get_user(user_id=2)
        self.assertEqual(unknown_user, None)


class TestFetch(base.TestWithDatabase):
    def test_paging(self) -> None:
        base._create_privilege(self.cursor, 1, "m_edit")
        base._create_privilege(self.cursor, 2, "m_delete")
        base._create_privilege(self.cursor, 3, "m_some_random")

        expected_privileges = [
            (
                0,
                [
                    {
                        "auth_option": "m_edit",
                        "auth_option_id": 1,
                        "founder_only": 0,
                        "is_global": 1,
                        "is_local": 0,
                    }
                ],
            ),
            (
                1,
                [
                    {
                        "auth_option": "m_delete",
                        "auth_option_id": 2,
                        "founder_only": 0,
                        "is_global": 1,
                        "is_local": 0,
                    }
                ],
            ),
            (
                2,
                [
                    {
                        "auth_option": "m_some_random",
                        "auth_option_id": 3,
                        "founder_only": 0,
                        "is_global": 1,
                        "is_local": 0,
                    }
                ],
            ),
            (3, []),
        ]

        for skip in range(0, 4):
            phpbb3: PhpBB3 = getattr(self.app, "phpbb3")
            privilege = phpbb3.fetch_acl_options(skip=skip, limit=1)
            self.assertEqual((skip, privilege), expected_privileges[skip])


class TestSession(base.TestWithDatabase):
    def setUp(self) -> None:
        super(TestSession, self).setUp()
        self.session_id = "123"

    def test_anonymous(self) -> None:
        data = self.client.get("/").get_data().decode("utf-8")
        self.assertEqual(data, "1,Anonymous")

    def test_invalid_session(self) -> None:
        base._create_user(self.cursor)

        data = self.client.get("/?sid=123").get_data().decode("utf-8")
        self.assertEqual(data, "1,Anonymous")

    def test_user_by_args(self) -> None:
        base._create_user(self.cursor)
        base._create_session(self.cursor, self.session_id, 2)

        data = self.client.get("/?sid=" + self.session_id).get_data().decode("utf-8")
        self.assertEqual(data, "2,test")

    def test_user_by_cookie(self) -> None:
        base._create_user(self.cursor)
        base._create_session(self.cursor, self.session_id, 2)

        self.client.set_cookie("phpbb3_sid", self.session_id, domain="127.0.0.1")
        data = self.client.get("/").get_data().decode("utf-8")
        self.assertEqual(data, "2,test")
        self.client.delete_cookie("phpbb3_sid", domain="127.0.0.1")

    def test_storage(self) -> None:
        base._create_user(self.cursor)
        base._create_session(self.cursor, self.session_id, 2)

        self.client.set_cookie("phpbb3_sid", self.session_id, domain="127.0.0.1")
        data = self.client.get("/data").get_data().decode("utf-8")
        self.assertEqual(data, "")

        self.client.get("/data/something")

        data = self.client.get("/data").get_data().decode("utf-8")
        self.assertEqual(data, "something")

    def test_storage_invalid_id(self) -> None:
        data = self.client.get("/data").get_data().decode("utf-8")
        self.assertEqual(data, "")

        self.client.get("/data/something")

        data = self.client.get("/data").get_data().decode("utf-8")
        self.assertEqual(data, "")

    def test_privilege(self) -> None:
        base._create_user(self.cursor)
        base._create_session(self.cursor, self.session_id, 2)
        base._create_privilege(self.cursor, 1, "m_edit")
        base._grant_privilege(self.cursor, 2)

        data = self.client.get("/priv_test").get_data().decode("utf-8")
        self.assertEqual(data, "False,False,False")

        # We do a login via phpbb3 :P
        self.client.set_cookie("phpbb3_sid", self.session_id, domain="127.0.0.1")

        data = self.client.get("/priv_test").get_data().decode("utf-8")
        self.assertEqual(data, "True,False,True")
