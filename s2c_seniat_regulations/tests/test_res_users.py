from odoo.exceptions import AccessDenied
from odoo.tests.common import TransactionCase


class TestResUsersCredentials(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_vals = {
            'name': 'Credentials Test User',
            'login': 'credentials_test_user',
            'password': 'credentials_test_password',
            'email': 'credentials_test_user@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        }
        if 'autopost_bills' in cls.env['res.users']._fields:
            user_vals['autopost_bills'] = 'ask'
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create(user_vals)

    def test_check_credentials_returns_auth_info(self):
        credential = {
            'type': 'password',
            'login': self.user.login,
            'password': 'credentials_test_password',
        }

        auth_info = self.user.with_user(self.user).sudo()._check_credentials(
            credential,
            {'interactive': True},
        )

        self.assertEqual(auth_info['uid'], self.user.id)

    def test_check_credentials_invalid_password_denied(self):
        credential = {
            'type': 'password',
            'login': self.user.login,
            'password': 'invalid_password',
        }

        with self.assertRaises(AccessDenied):
            self.user.with_user(self.user).sudo()._check_credentials(
                credential,
                {'interactive': True},
            )