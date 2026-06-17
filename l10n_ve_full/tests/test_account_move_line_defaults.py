from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountMoveLineDefaults(TransactionCase):

    def test_default_islr_concept_id_uses_expected_xmlid(self):
        default_concept = self.env['account.move.line']._default_islr_concept_id()

        self.assertEqual(
            default_concept,
            self.env.ref('l10n_ve_full.islr_wh_concept_no_apply_withholding'),
        )

    def test_default_islr_concept_id_is_safe_when_xmlid_is_missing(self):
        with patch.object(type(self.env), 'ref', autospec=True, return_value=False) as ref:
            default_concept = self.env['account.move.line']._default_islr_concept_id()

        self.assertFalse(default_concept)
        ref.assert_called_once_with(
            self.env,
            'l10n_ve_full.islr_wh_concept_no_apply_withholding',
            raise_if_not_found=False,
        )