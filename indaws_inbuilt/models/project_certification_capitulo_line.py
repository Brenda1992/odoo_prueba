# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectCertificationCapituloLine(models.Model):
    _name = 'project.certification.capitulo.line'
    _description = 'Capitulos en Certificacion'
    _order = 'sale_order, capitulo_id'

    certification_id = fields.Many2one('project.certification', string='Certificacion', required=True, ondelete='cascade')
    capitulo_id = fields.Many2one('sale.capitulo', string='Capítulo')
    sale_order = fields.Many2one('sale.order', related='capitulo_id.order_id', string='Pedido Venta')
    currency_id = fields.Many2one(related='certification_id.currency_id', string='Moneda', tracking=True)
    price_subtotal = fields.Monetary(related='capitulo_id.price_subtotal', string='Presupuesto', currency_field='currency_id')
    certified = fields.Monetary(string='Cert.Origen', compute='compute_capitulo_certification')
    before_certified = fields.Monetary(string='Cert.Anterior', compute='compute_capitulo_certification')
    current_certified = fields.Monetary(string='Cert.Actual', compute='compute_capitulo_certification')
    company_id = fields.Many2one('res.company', string='Company', related="certification_id.company_id")

    @api.depends('certification_id.importe_certificado','certification_id.importe_certificado_actual','certification_id.certified_before')
    def compute_capitulo_certification(self):
        for capitulo in self:
            price_subtotal = 0
            certified = 0
            before_certified = 0
            current_certified = 0

            lines = capitulo.certification_id.line_ids.filtered(lambda line: line.capitulo_id == capitulo.capitulo_id)
            if lines:
                price_subtotal = sum(lines.mapped('price_subtotal'))
                certified = sum(lines.mapped('certified'))
                current_certified = sum(lines.mapped('current_certified'))
                before_certified = sum(lines.mapped('certified_before'))

            capitulo.update({
                'price_subtotal':price_subtotal,
                'certified':certified,
                'before_certified':before_certified,
                'current_certified':current_certified,
            })