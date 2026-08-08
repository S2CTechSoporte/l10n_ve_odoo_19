from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVenezuelaOwnData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve_country = cls.env.ref('base.ve')
        cls.ves_currency = cls.env.ref('base.VES')
        cls.company_partner = cls.env['res.partner'].create({
            'name': 'Own Data Venezuela Company',
            'is_company': True,
            'company_type': 'company',
            'people_type_company': 'pjdo',
            'vat': 'J876543213',
            'country_id': cls.ve_country.id,
            'wh_iva_agent': False,
            'islr_withholding_agent': False,
        })
        cls.company = cls.env['res.company'].create({
            'name': 'Own Data Venezuela Company',
            'partner_id': cls.company_partner.id,
            'country_id': cls.ve_country.id,
            'currency_id': cls.ves_currency.id,
            'currency_l10n_id': cls.ves_currency.id,
        })

    def test_own_company_has_venezuelan_rif_and_currencies(self):
        validated_vat, country_code = self.env['res.partner']._run_vat_checks(
            self.ve_country, self.company.vat,
        )

        self.assertEqual(self.company.country_id, self.ve_country)
        self.assertEqual(self.company.currency_id, self.ves_currency)
        self.assertEqual(self.company.currency_l10n_id, self.ves_currency)
        self.assertEqual(validated_vat, self.company.vat)
        self.assertEqual(country_code, 'VE')
        self.assertTrue(self.company.vat.startswith('J'))