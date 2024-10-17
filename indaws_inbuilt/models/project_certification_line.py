# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectCertificationLine(models.Model):
    _name = 'project.certification.line'
    _description = 'Linea Certificacion'
    _order = 'sequence, sale_order, capitulo_id'

    sequence = fields.Integer(string="Sequence", default=10)
    certification_id = fields.Many2one('project.certification', string='Certificacion', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='certification_id.currency_id', string='Moneda', tracking=True)
    project_production_line_id = fields.Many2one('project.production',string='Linea Producción', tracking=True)
    sale_line_id = fields.Many2one('sale.order.line', related='project_production_line_id.sale_line_id', string='Linea Pedido', required=False, store=True, tracking=True)
    sale_order = fields.Many2one('sale.order',string='Presupuesto', related='sale_line_id.order_id', store=True, tracking=True)
    capitulo_id = fields.Many2one('sale.capitulo', string='Capítulo', related='project_production_line_id.capitulo_id', store=True, tracking=True)
    name = fields.Char(related='project_production_line_id.name', store=True, readonly=False, tracking=True) #traido de project_certification_modification
    price_subtotal = fields.Monetary(related='project_production_line_id.price_subtotal', string='Precio de venta', currency_field='currency_id', tracking=True)#traido de project_certification_modification
    price_unit = fields.Monetary(related='project_production_line_id.price_unit', string='Precio unitario', currency_field='currency_id', tracking=True)#traido de project_certification_modification
    quantity = fields.Float(string="Cantidad", related='project_production_line_id.quantity', dp='Product Unit of Measure', tracking=True)

    certified = fields.Monetary(string='Cert.Origen', tracking=True)
    ptje = fields.Float(string='% Cert.Origen', dp='Product Unit of Measure', tracking=True)
    quantity_certified = fields.Float(string="Cantidad Cert.Origen", dp='Product Unit of Measure', tracking=True)

    current_certified = fields.Monetary(string='Cert.Actual', compute='_current_certified', tracking=True)
    quantity_current_certified = fields.Float(string="Cantidad Cert.Actual", compute="_current_certified", tracking=True, dp='Product Unit of Measure')
    current_certified_ptje = fields.Float(string='% Cert.Actual', compute='_current_certified', dp='Product Unit of Measure', tracking=True)

    certified_before = fields.Monetary(string='Cert.Anterior', compute='_previous_certified', tracking=True)
    certified_before_ptje = fields.Float(string='% Cert.Anterior', readonly=True, compute='_previous_certified', dp='Product Unit of Measure', tracking=True)
    quantity_certified_before = fields.Float(string="Cantidad Cert.Anterior", compute="_previous_certified", dp='Product Unit of Measure', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    red_line = fields.Boolean('red line', compute='_previous_certified')


    @api.onchange('ptje')
    def onchange_ptje(self):
        if self.ptje < 0 or self.ptje > 100:
            raise ValidationError(_('El % Certificado debe der mayor a 0 y no puede ser mayor a 100'))

        if self.env.context.get('propagation',True):
            certified = self.price_subtotal * (self.ptje / 100)
            quantity_certified = self.quantity * (self.ptje / 100)

            self.with_context(propagation=False).update({
                'certified':certified,
                'quantity_certified':quantity_certified,
            })

    @api.onchange('certified')
    def onchange_certified(self):
        if self.env.context.get('propagation', True):
            ptje = (self.certified / self.price_subtotal) * 100 if self.price_subtotal != 0 else 0
            quantity_certified = self.quantity * (ptje / 100)

            self.with_context(propagation=False).update({
                'ptje': ptje,
                'quantity_certified': quantity_certified,
            })

    @api.depends('certified', 'certified_before')
    def _current_certified(self):
        for rec in self:
            rec.current_certified = rec.certified - rec.certified_before
            rec.quantity_current_certified = rec.quantity_certified - rec.quantity_certified_before
            rec.current_certified_ptje = rec.ptje - rec.certified_before_ptje

    @api.onchange('quantity_certified')
    def onchange_quantity_certified(self):
        if self.env.context.get('propagation', True):
            ptje = (self.quantity_certified / self.quantity) * 100 if self.quantity != 0 else 0
            certified = self.price_subtotal * (ptje / 100)

            self.with_context(propagation=False).update({
                'certified': certified,
                'ptje': ptje,
            })

    @api.depends('certification_id', 'certification_id.project_id')
    def _previous_certified(self):
        for rec in self:
            certified_before = 0
            certified_before_ptje = 0
            quantity_certified_before = 0

            secuencia = rec.certification_id.sequence - 1
            if secuencia >= 1:
                previous_record = self.env['project.certification'].search([('project_id', '=', rec.certification_id.project_id.id), ('sequence', '=', secuencia)], limit=1, order='id desc')
                if previous_record.project_id == rec.certification_id.project_id and rec.certification_id.project_id:
                    previous_line = previous_record.line_ids.filtered(lambda line: line.project_production_line_id == rec.project_production_line_id)
                    if previous_line:
                        certified_before = previous_line[0].certified
                        certified_before_ptje = previous_line[0].ptje
                        quantity_certified_before = previous_line[0].quantity_certified

            rec.with_context(propagation=False).update({
                'certified_before': certified_before,
                'certified_before_ptje': certified_before_ptje,
                'quantity_certified_before': quantity_certified_before,
                'red_line': True if rec.certified < certified_before else False
            })


    @api.onchange('certified')
    def onchange_certified_validation(self):
        for rec in self:
            if rec.certified_before > rec.certified:
                raise ValidationError(_('Error: el importe certificado no puede ser inferior al importe certificado previo'))
            if rec.certified > rec.price_subtotal:
                rec.certified = 0
                raise ValidationError(_('Error: el importe certificado no puede ser mayor al precio de venta.'))
