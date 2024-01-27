# -*- coding: utf-8 -*-
#
#   l10n_co_hr_payroll
#   Copyright (C) 2023  Jorels SAS
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#   email: info@jorels.com
#

import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class EdiGen(models.TransientModel):
    _name = 'l10n_co_hr_payroll.edi_gen'
    _description = 'Generate Edi Payslips'

    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December')
    ], string='Month', required=True, default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.context_today(self).year)

    # It only works for one contract per employee.
    # If an employee's payroll has multiple contracts, then the generated payroll will grab the last contract it finds.
    @api.multi
    def generate(self, options):
        payslip_env = self.env['hr.payslip']
        edi_payslip_env = self.env['hr.payslip.edi']

        # Existing Payslips
        payslip_recs = payslip_env.search([
            ('year', '=', int(self.year)),
            ('month', '=', self.month),
            ('credit_note', '=', False),
            ('origin_payslip_id', '=', False),
            ('state', '!=', 'draft')
        ])

        # Existing Credit notes
        credit_note_recs = payslip_env.search([
            ('year', '=', int(self.year)),
            ('month', '=', self.month),
            ('credit_note', '=', True),
            ('origin_payslip_id', '!=', False),
            ('state', '!=', 'draft')
        ])

        # Filtered valid Payslips
        origin_payslip_list = []
        for credit_note_rec in credit_note_recs:
            origin_payslip_list.append(credit_note_rec.origin_payslip_id.id)
        valid_edi_payslips = payslip_recs.filtered(lambda payslip: payslip.id not in origin_payslip_list)

        # Delete existing Edi Payslips in draft state
        for_delete_edi_payslip_recs = edi_payslip_env.search([
            ('year', '=', int(self.year)),
            ('month', '=', self.month),
            ('state', '=', 'draft')
        ])
        for_delete_edi_payslip_recs.unlink()

        # Creating new Edi Payslips in draft state without payslips
        for new_edi_payslip in valid_edi_payslips:
            existing_edi_payslip_recs = edi_payslip_env.search([
                ('year', '=', int(self.year)),
                ('month', '=', self.month),
                ('employee_id', '=', new_edi_payslip.employee_id.id)
            ])
            if not existing_edi_payslip_recs:
                edi_payslip_env.create({
                    'year': int(self.year),
                    'month': self.month,
                    'employee_id': new_edi_payslip.employee_id.id,
                })

        # Adding Payslips to Edi Payslips
        # Search for existing Edi Payslips in draft state
        existing_edi_payslip_recs = edi_payslip_env.search([
            ('year', '=', int(self.year)),
            ('month', '=', self.month),
            ('state', '=', 'draft')
        ])
        for existing_edi_payslip_rec in existing_edi_payslip_recs:
            # Filtered new Edi Payslips for an employee
            new_edi_payslips_employee = valid_edi_payslips.filtered(
                lambda payslip: payslip.employee_id.id == existing_edi_payslip_rec.employee_id.id
            )

            # First remove existing Payslips in Edi Payslip
            for new_edi_payslip_employee in new_edi_payslips_employee:
                new_edi_payslip_employee.write({'payslip_ids': [(5,)]})

            # Then add Payslips to Edi Payslip
            for new_edi_payslip_employee in new_edi_payslips_employee:
                existing_edi_payslip_rec.write({
                    'payslip_ids': [(4, new_edi_payslip_employee.id)],
                    'contract_id': new_edi_payslip_employee.contract_id.id
                })

        # To update or redirect to the Edi Payslip view
        return {
            "name": "Edi Payslips",
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip.edi",
            "views": [[False, "tree"], [False, "form"]],
        }
