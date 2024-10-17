# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    certification_id = fields.Many2one('project.certification', 'Certificación')
    project_id = fields.Many2one('project.project', string='Obra', compute='_compute_project_id', store=True)

    def unlink(self):
        for rec in self:
            certification_id = self.env['project.certification'].search([
                ('move_id', '=', rec.id)])
            if certification_id:
                certification_id.state = 'draft'
        return super(AccountMove, self).unlink()

    @api.depends('invoice_line_ids', 'invoice_line_ids.analytic_distribution')
    def _compute_project_id(self):
        for move in self:
            project_id = move.project_id
            if not project_id and move.invoice_line_ids.filtered(lambda l: l.analytic_distribution):
                for line in move.invoice_line_ids.filtered(lambda l: l.analytic_distribution):
                    for account_id, distribution in line.analytic_distribution.items():
                        project_id = self.env['project.project'].search([('analytic_account_id','=',account_id)])
                        break
            move.write({'project_id': project_id})
