from odoo import models, fields, api
from odoo.exceptions import AccessDenied

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, password, env):
        try:
            super(ResUsers, self)._check_credentials(password, env)
            self.env['ir.logging'].create({
                'name': 'Login Attempt',
                'type': 'server',
                'dbname': self.env.cr.dbname,
                'level': 'INFO',
                'message': f"User {self.login} logged in successfully",
                'path': 'res.users',
                'func': '_check_credentials',
                'line': 0,
            })
        except AccessDenied:
            self.env['ir.logging'].create({
                'name': 'Login Attempt',
                'type': 'server',
                'dbname': self.env.cr.dbname,
                'level': 'WARNING',
                'message': f"Access denied for user {self.login}",
                'path': 'res.users',
                'func': '_check_credentials',
                'line': 0,
            })
            self.env.cr.commit()
            raise
