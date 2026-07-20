from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from unittest.mock import patch

from odoo.addons.l10n_ve_full.models.res_partner import RIF_CHECKSUM_ERROR, RIF_FORMAT_ERROR


@tagged('post_install', '-at_install')
class TestRifVatValidation(TransactionCase):

    def test_partner_rif_validation_accepts_compact_value(self):
        Partner = self.env['res.partner']

        self.assertTrue(Partner.validate_rif_er('V151005809'))

    def test_company_vat_validation_accepts_compact_value(self):
        Company = self.env['res.company']

        self.assertTrue(Company.validate_vat_er('V151005809'))

    def test_ve_rif_format_error_message_uses_compact_mask(self):
        Partner = self.env['res.partner']

        with self.assertRaises(ValidationError) as error:
            Partner._run_vat_checks(
                self.env.ref('base.ve'),
                'J-40970891-1',
                partner_name='test 4',
            )

        message = str(error.exception)
        self.assertEqual(message, RIF_FORMAT_ERROR)

    def test_ve_rif_checksum_error_message_uses_compact_mask(self):
        Partner = self.env['res.partner']

        with self.assertRaises(ValidationError) as error:
            Partner._run_vat_checks(
                self.env.ref('base.ve'),
                'J409708911',
                partner_name='test 4',
            )

        self.assertEqual(str(error.exception), RIF_CHECKSUM_ERROR)

    def test_rif_validation_rejects_invalid_values(self):
        invalid_rifs = (
            '151005809',
            'V-15100580-9',
            'V15100580-9',
            'V-15.100.580-9',
            'V15100580',
        )
        for rif in invalid_rifs:
            with self.subTest(rif=rif):
                with self.assertRaises(UserError):
                    self.env['res.partner'].validate_rif_er(rif)
                with self.assertRaises(UserError):
                    self.env['res.company'].validate_vat_er(rif)

    def test_company_write_preserves_compact_vat(self):
        company = self.env.company
        company.country_id = self.env.ref('base.ve')

        company.vat = 'J876543213'

        self.assertEqual(company.vat, 'J876543213')
        self.assertEqual(company.rif, 'J876543213')
        self.assertTrue(company.validate_vat_er('V151005809'))

    def test_non_ve_company_vat_skips_ve_rif_constraint(self):
        partner = self.env['res.partner'].new({
            'name': 'Foreign Company',
            'company_type': 'company',
            'people_type_company': 'pjdo',
            'country_id': self.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })

        with patch.object(type(partner), 'validate_rif_er', side_effect=AssertionError('validate_rif_er should not be called')):
            with patch.object(type(partner), 'validate_rif_duplicate', side_effect=AssertionError('validate_rif_duplicate should not be called')):
                partner._check_rif()
