# -*- coding: utf-8 -*-
#
# Jorels S.A.S. - Copyright (2019-2022)
#
# This file is part of l10n_co_edi_jorels.
#
# l10n_co_edi_jorels is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# l10n_co_edi_jorels is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with l10n_co_edi_jorels.  If not, see <https://www.gnu.org/licenses/>.
#
# email: info@jorels.com
#

import json
import logging

import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Radian(models.Model):
    _name = "l10n_co_edi_jorels.radian"
    _description = "Radian events"

    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', required=True, readonly=True, copy=False, tracking=True, default='draft')
    date = fields.Date("Date", required=True, readonly=True, default=fields.Date.context_today, copy=False)
    event_id = fields.Many2one(comodel_name="l10n_co_edi_jorels.events", string="Event", required=True, readonly=True,
                               tracking=True, ondelete='RESTRICT', states={'draft': [('readonly', False)]},
                               domain=[('code', 'in', ['030', '031', '032', '033', '034'])])
    name = fields.Char(string="Reference", compute="_compute_name", store=True, copy=False, readonly=True,
                       default=lambda self: _("New"))
    number = fields.Integer(string="Number", readonly=True, states={'draft': [('readonly', False)]}, tracking=True,
                            copy=False)
    prefix = fields.Char(string="Prefix", readonly=True, states={'draft': [('readonly', False)]}, tracking=True,
                         copy=False)
    note = fields.Text(string="Note", readonly=True, states={'draft': [('readonly', False)]})
    rejection_concept_id = fields.Many2one(comodel_name="l10n_co_edi_jorels.rejection_concepts",
                                           string="Rejection concept", required=False, readonly=True,
                                           ondelete='RESTRICT', states={'draft': [('readonly', False)]}, tracking=True,
                                           copy=False)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
                                 default=lambda self: self.env['res.company']._company_default_get(),
                                 states={'draft': [('readonly', False)]})
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice", required=True, readonly=True,
                                 states={'draft': [('readonly', False)]}, copy=False,
                                 domain=[('type', 'in', ['in_invoice', 'in_refund']),
                                         ('state', 'not in', ['draft', 'cancel'])], tracking=True)

    # Storing synchronous and production modes
    edi_sync = fields.Boolean(string="Sync", default=False, copy=False, readonly=True)
    edi_is_not_test = fields.Boolean(string="In production", copy=False, readonly=True,
                                     default=lambda self: self.env[
                                         'res.company'
                                     ]._company_default_get().is_not_test, store=True,
                                     compute="_compute_ei_is_not_test")

    # Edi response fields
    edi_is_valid = fields.Boolean("Is valid?", copy=False, readonly=True)
    edi_is_restored = fields.Boolean("Is restored?", copy=False, readonly=True)
    edi_algorithm = fields.Char("Algorithm", copy=False, readonly=True)
    edi_class = fields.Char("Class", copy=False, readonly=True)
    edi_number = fields.Char("Number", copy=False, readonly=True)
    edi_uuid = fields.Char("UUID", copy=False, readonly=True)
    edi_issue_date = fields.Date("Date", copy=False, readonly=True)
    edi_expedition_date = fields.Char("Expedition date", copy=False, readonly=True)
    edi_zip_key = fields.Char("Zip key", copy=False, readonly=True)
    edi_status_code = fields.Char("Status code", copy=False, readonly=True)
    edi_status_description = fields.Char("Status description", copy=False, readonly=True)
    edi_status_message = fields.Char("Status message", copy=False, readonly=True)
    edi_errors_messages = fields.Char("Error messages", copy=False, readonly=True)
    edi_xml_name = fields.Char("XML name", copy=False, readonly=True)
    edi_zip_name = fields.Char("Zip name", copy=False, readonly=True)
    edi_signature = fields.Char("Signature", copy=False, readonly=True)
    edi_qr_code = fields.Char("QR code", copy=False, readonly=True)
    edi_qr_data = fields.Char("QR data", copy=False, readonly=True)
    edi_qr_link = fields.Char("QR link", copy=False, readonly=True)
    edi_pdf_download_link = fields.Char("PDF link", copy=False, readonly=True)
    edi_xml_base64 = fields.Binary("XML", copy=False, readonly=True)
    edi_application_response_base64 = fields.Binary("Application response", copy=False, readonly=True)
    edi_attached_document_base64 = fields.Binary("Attached document", copy=False, readonly=True)
    edi_pdf_base64 = fields.Binary("PDF", copy=False, readonly=True)
    edi_zip_base64 = fields.Binary("Zip document", copy=False, readonly=True)
    edi_type_environment = fields.Many2one(comodel_name="l10n_co_edi_jorels.type_environments",
                                           string="Type environment", copy=False, readonly=True)
    edi_payload = fields.Text("Payload", copy=False, readonly=True)

    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              readonly=True, states={'draft': [('readonly', False)]},
                              default=lambda self: self.env.user, copy=False)

    @api.depends("edi_type_environment")
    def _compute_edi_is_not_test(self):
        for rec in self:
            if rec.edi_type_environment:
                rec.edi_is_not_test = (rec.edi_type_environment.id == 1)
            else:
                rec.edi_is_not_test = rec.company_id.is_not_test

    @api.depends("prefix", "number")
    def _compute_name(self):
        for rec in self:
            if rec.prefix and rec.number:
                rec.name = rec.prefix + str(rec.number)
            else:
                rec.name = _("New")

    @api.multi
    def write_response(self, response, payload):
        for rec in self:
            rec.edi_is_valid = response['is_valid']
            rec.edi_is_restored = response['is_restored']
            rec.edi_algorithm = response['algorithm']
            rec.edi_class = response['class']
            rec.edi_number = response['number']
            rec.edi_uuid = response['uuid']
            rec.edi_issue_date = response['issue_date']
            rec.edi_expedition_date = response['expedition_date']
            rec.edi_zip_key = response['zip_key']
            rec.edi_status_code = response['status_code']
            rec.edi_status_description = response['status_description']
            rec.edi_status_message = response['status_message']
            rec.edi_errors_messages = str(response['errors_messages'])
            rec.edi_xml_name = response['xml_name']
            rec.edi_zip_name = response['zip_name']
            rec.edi_signature = response['signature']
            rec.edi_qr_code = response['qr_code']
            rec.edi_qr_data = response['qr_data']
            rec.edi_qr_link = response['qr_link']
            rec.edi_pdf_download_link = response['pdf_download_link']
            rec.edi_xml_base64 = response['xml_base64_bytes']
            rec.edi_application_response_base64 = response['application_response_base64_bytes']
            rec.edi_attached_document_base64 = response['attached_document_base64_bytes']
            rec.edi_pdf_base64 = response['pdf_base64_bytes']
            rec.edi_zip_base64 = response['zip_base64_bytes']
            rec.edi_type_environment = response['type_environment_id']
            rec.edi_payload = payload

    @api.multi
    def action_post(self):
        for rec in self:
            # Sequence
            name_sequence = 'radian_' + rec.event_id.code
            prefix = "E" + rec.event_id.code

            if not rec.name or rec.name in ('New', _('New')):
                rec.name = rec.env['ir.sequence'].next_by_code(name_sequence)

            if rec.name and rec.name not in ('New', _('New')) and rec.name[0:4] == prefix:
                rec.number = ''.join([i for i in rec.name[4:] if i.isdigit()])
                rec.prefix = prefix

            if not rec.number or not rec.prefix:
                raise UserError(_("The DIAN event sequence is wrong."))

            # Posted
            rec.write({'state': 'posted'})

            # Validate DIAN
            if rec.company_id.ei_enable:
                rec.validate_dian_generic()

        return True

    # @api.multi
    # def action_status(self):
    #     for rec in self:
    #         raise UserError("No implementado")

    @api.multi
    def action_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
        return True

    @api.multi
    def action_cancel(self):
        for rec in self:
            if not rec.edi_is_valid:
                rec.write({'state': 'cancel'})
            else:
                raise UserError(_("You cannot cancel a Radian event that has already been validated to the DIAN"))
        return True

    @api.multi
    def get_json_request(self):
        for rec in self:
            if rec.event_id.code == '031' and not rec.rejection_concept_id:
                raise UserError(_("The rejection concept is required for the DIAN claim event."))
            if not rec.invoice_id.ei_uuid:
                raise UserError(_("The invoice UUID (CUFE) is required for DIAN events."))
            if not rec.user_id.partner_id.type_document_identification_id:
                raise UserError(_("The document type for user is required for DIAN events."))
            if not rec.user_id.partner_id.vat:
                raise UserError(_("The document number (VAT) for user is required for DIAN events."))
            if not rec.user_id.first_name:
                raise UserError(_("The user first name is required for DIAN events"))
            if not rec.user_id.surname:
                raise UserError(_("The user surname is required for DIAN events"))
            if not rec.number or not rec.prefix:
                raise UserError(_("The number and prefix are required for DIAN events"))

            json_request = {
                "prefix": rec.prefix,
                "number": rec.number,
                "sync": rec.company_id.is_not_test,
                "uuid": rec.invoice_id.ei_uuid,
                "person": {
                    "id_code": rec.user_id.partner_id.type_document_identification_id.id,
                    "id_number": ''.join([i for i in rec.user_id.partner_id.vat if i.isdigit()]),
                    "first_name": rec.user_id.first_name,
                    "surname": rec.user_id.surname,
                    "job_title": "Asistente de contabilidad",
                    "country_code": 46,
                    "company_department": "Contabilidad"
                },
            }

            if rec.event_id.code == '031' and rec.rejection_concept_id:
                json_request['rejection_code'] = rec.rejection_concept_id.id

            # Notes
            if rec.note:
                notes = [{
                    "text": rec.note
                }]
                json_request['notes'] = notes

        return json_request

    @api.multi
    def validate_dian_generic(self):
        for rec in self:
            try:
                if not rec.company_id.ei_enable:
                    continue

                requests_data = rec.get_json_request()

                # Payload
                payload = json.dumps(requests_data, indent=2, sort_keys=False)

                # API key and URL
                if rec.company_id.api_key:
                    token = rec.company_id.api_key
                else:
                    raise UserError(_("You must configure a token"))

                api_url = self.env['ir.config_parameter'].sudo().get_param('jorels.edipo.api_url',
                                                                           'https://edipo.jorels.com')
                params = {
                    'token': token,
                    'code': rec.event_id.code
                }
                header = {"accept": "application/json", "Content-Type": "application/json"}

                # Request
                api_url = api_url + "/basic_event"

                rec.edi_is_not_test = rec.company_id.is_not_test

                if not rec.edi_is_not_test:
                    if rec.company_id.test_set_id:
                        params['test_set_id'] = rec.company_id.test_set_id
                    else:
                        raise UserError(_("You have not configured a 'TestSetId'."))

                _logger.debug('API URL: %s', api_url)
                _logger.debug("DIAN Validation Request: %s", json.dumps(requests_data, indent=2, sort_keys=False))
                # raise Warning(json.dumps(requests_data, indent=2, sort_keys=False))

                response = requests.post(api_url,
                                         json.dumps(requests_data),
                                         headers=header,
                                         params=params).json()
                _logger.debug('API Response: %s', response)

                if 'detail' in response:
                    raise UserError(response['detail'])
                if 'message' in response:
                    if response['message'] == 'Unauthenticated.' or response['message'] == '':
                        raise UserError(_("Authentication error with the API"))
                    else:
                        if 'errors' in response:
                            raise UserError(response['message'] + '/ errors: ' + str(response['errors']))
                        else:
                            raise UserError(response['message'])
                elif 'is_valid' in response:
                    rec.write_response(response, payload)
                    if response['is_valid']:
                        self.env.user.notify_success(message=_("The validation at DIAN has been successful."))
                    elif 'zip_key' in response:
                        if response['zip_key'] is not None:
                            if not rec.edi_is_not_test:
                                self.env.user.notify_success(message=_("Document sent to DIAN in habilitation."))
                            else:
                                temp_message = {rec.edi_status_message, rec.edi_errors_messages,
                                                rec.edi_status_description, rec.edi_status_code}
                                raise UserError(str(temp_message))
                        else:
                            raise UserError(_('A valid Zip key was not obtained. Try again.'))
                    else:
                        raise UserError(_('The document could not be validated in DIAN.'))
                else:
                    raise UserError(_("No logical response was obtained from the API."))
            except Exception as e:
                _logger.debug("Failed to process the request: %s", e)
                raise UserError(_("Failed to process the request: %s") % e)
