from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from unittest.mock import patch


@tagged('post_install', '-at_install')
class TestRifVatValidation(TransactionCase):

    def test_partner_rif_validation_accepts_hyphenated_and_compact_values(self):
        Partner = self.env['res.partner']

        self.assertTrue(Partner.validate_rif_er('V-15100580-9'))
        self.assertTrue(Partner.validate_rif_er('V151005809'))

    def test_company_vat_validation_accepts_hyphenated_and_compact_values(self):
        Company = self.env['res.company']

        self.assertTrue(Company.validate_vat_er('V-15100580-9'))
        self.assertTrue(Company.validate_vat_er('V151005809'))

    def test_ve_rif_checksum_error_message_is_clear(self):
        Partner = self.env['res.partner']

        with self.assertRaises(ValidationError) as error:
            Partner._run_vat_checks(
                self.env.ref('base.ve'),
                'J-40970891-1',
                partner_name='test 4',
            )

        message = str(error.exception)
        self.assertIn('dígito verificador', message)
        self.assertIn('Revise que la letra, el número y el último dígito', message)
        self.assertNotIn('formato esperado', message.lower())

    def test_rif_validation_rejects_invalid_values(self):
        with self.assertRaises(UserError):
            self.env['res.partner'].validate_rif_er('151005809')

        with self.assertRaises(UserError):
            self.env['res.company'].validate_vat_er('151005809')

    def test_company_write_preserves_hyphenated_vat(self):
        company = self.env.company
        company.country_id = self.env.ref('base.ve')

        company.vat = 'J-87654321-3'

        self.assertEqual(company.vat, 'J-87654321-3')
        self.assertEqual(company.rif, 'J-87654321-3')
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
