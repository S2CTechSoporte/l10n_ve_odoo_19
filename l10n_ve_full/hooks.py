def post_init_hook(env):
    """Align stored partner fiscal defaults with countries already in the database."""
    env.cr.execute(
        """
        UPDATE res_partner
           SET nationality = NULL,
               people_type_individual = NULL,
               people_type_company = NULL
         WHERE country_id IS NULL
        """
    )
    env.cr.execute(
        """
        UPDATE res_partner AS partner
           SET nationality = CASE WHEN country.code = 'VE' THEN 'V' ELSE 'E' END,
               people_type_individual = CASE
                   WHEN country.code = 'VE' THEN 'pnre' ELSE 'pnnr'
               END,
               people_type_company = CASE
                   WHEN country.code = 'VE' THEN 'pjdo' ELSE 'pjnd'
               END
          FROM res_country AS country
         WHERE partner.country_id = country.id
        """
    )
    env['res.partner'].invalidate_model([
        'nationality',
        'people_type_individual',
        'people_type_company',
    ])