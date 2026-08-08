from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPartnerDefaults(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.ve_country = cls.env.ref('base.ve')
        cls.us_country = cls.env.ref('base.us')

    def test_nationality_follows_country_on_create(self):
        no_country_partner = self.Partner.create({
            'name': 'Partner Without Country',
            'country_id': False,
        })
        venezuelan_partner = self.Partner.create({
            'name': 'Venezuelan Partner',
            'country_id': self.ve_country.id,
        })
        foreign_partner = self.Partner.create({
            'name': 'Foreign Partner',
            'country_id': self.us_country.id,
        })

        self.assertFalse(no_country_partner.nationality)
        self.assertFalse(no_country_partner.people_type_individual)
        self.assertFalse(no_country_partner.people_type_company)
        self.assertEqual(venezuelan_partner.nationality, 'V')
        self.assertEqual(venezuelan_partner.people_type_individual, 'pnre')
        self.assertEqual(venezuelan_partner.people_type_company, 'pjdo')
        self.assertEqual(foreign_partner.nationality, 'E')
        self.assertEqual(foreign_partner.people_type_individual, 'pnnr')
        self.assertEqual(foreign_partner.people_type_company, 'pjnd')

    def test_nationality_default_follows_effective_country(self):
        default_partner = self.Partner.new({})
        no_country_partner = self.Partner.with_context(default_country_id=False).new({})
        foreign_partner = self.Partner.with_context(
            default_country_id=self.us_country.id,
        ).new({})

        self.assertEqual(default_partner.nationality, 'V')
        self.assertEqual(default_partner.people_type_individual, 'pnre')
        self.assertEqual(default_partner.people_type_company, 'pjdo')
        self.assertFalse(no_country_partner.nationality)
        self.assertFalse(no_country_partner.people_type_individual)
        self.assertFalse(no_country_partner.people_type_company)
        self.assertEqual(foreign_partner.nationality, 'E')
        self.assertEqual(foreign_partner.people_type_individual, 'pnnr')
        self.assertEqual(foreign_partner.people_type_company, 'pjnd')

    def test_nationality_follows_country_on_write(self):
        partner = self.Partner.create({
            'name': 'Partner Country Changes',
            'country_id': False,
        })

        partner.write({'country_id': self.ve_country.id})
        self.assertEqual(partner.nationality, 'V')
        self.assertEqual(partner.people_type_individual, 'pnre')
        self.assertEqual(partner.people_type_company, 'pjdo')

        partner.write({'country_id': self.us_country.id})
        self.assertEqual(partner.nationality, 'E')
        self.assertEqual(partner.people_type_individual, 'pnnr')
        self.assertEqual(partner.people_type_company, 'pjnd')

        partner.write({'country_id': False})
        self.assertFalse(partner.nationality)
        self.assertFalse(partner.people_type_individual)
        self.assertFalse(partner.people_type_company)

    def test_nationality_follows_country_onchange(self):
        partner = self.Partner.new({
            'name': 'Partner Onchange',
            'country_id': self.us_country.id,
        })

        partner._onchange_country_id_set_nationality()

        self.assertEqual(partner.nationality, 'E')
        self.assertEqual(partner.people_type_individual, 'pnnr')
        self.assertEqual(partner.people_type_company, 'pjnd')

    def test_existing_demo_partner_defaults_follow_country(self):
        partner = self.env.ref('base.partner_demo_portal', raise_if_not_found=False)
        if not partner:
            self.skipTest('This check requires Odoo demo data')

        self.assertEqual(partner.country_id, self.us_country)
        self.assertEqual(partner.nationality, 'E')
        self.assertEqual(partner.people_type_individual, 'pnnr')
        self.assertEqual(partner.people_type_company, 'pjnd')