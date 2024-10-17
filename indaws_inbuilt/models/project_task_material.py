# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class ProjectTaskMaterial(models.Model):
    _name = 'project.task.material'
    _description = 'Materiales proyecto'

    #TODO sacar warning al borrar

    task_id = fields.Many2one('project.task', string='Tarea')
    project_id = fields.Many2one('project.project', string='Project', store=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True, domain=[('type', 'in', ['consu', 'product'])])
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency of the Payment Transaction",
        required=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )
    comment = fields.Char(string='Notas')
    quantity = fields.Float(string='Cantidad', default=1)
    cost = fields.Monetary(string='Coste ud')
    cost_subtotal = fields.Monetary('Precio de Coste', compute='_compute_cost_subtotal')
    sent = fields.Boolean(string='Enviado?', default=False)
    analytic_move_id = fields.Many2one('account.analytic.line', string='Movimiento analitico')
    picking_id = fields.Many2one('stock.picking', 'Albaran')
    location_id = fields.Many2one('stock.location', 'Ubicacion Orig.')
    location_dest_id = fields.Many2one('stock.location', 'Ubicacion Dest.')
    product_uom_id = fields.Many2one('uom.uom', string="Unidad Medida" )
    qty_available = fields.Float(string="Stock", related="product_id.qty_available")
    picking_state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Estado albarán', related="picking_id.state")
    price_unit = fields.Monetary(string="Precio ud", default=lambda self: self.product_id.list_price)
    total_price = fields.Monetary(string="Precio de Venta", compute='compute_total_price')
    sale_order_line_id = fields.Many2one('sale.order.line', string="Sale Line Id")
    sale_unidad_obra_id = fields.Many2one('sale.unidad.obra', string="Sale Unidad Obra", copy=False)
    sale_id = fields.Many2one('sale.order')
    origin_id = fields.Many2one('purchase.order', string="Document Origin")
    origin_line_id = fields.Many2one('purchase.order.line', string="Document Origin Line")
    product_qty_purchase = fields.Float(string='Compra', related="origin_line_id.product_qty")
    qty_received = fields.Float(string='Cantidad recibida', compute='_compute_qty_received')
    date_planned = fields.Datetime(string='Entrega esperada', related="origin_line_id.date_planned")



    @api.depends('picking_id', 'picking_state', 'origin_line_id', 'origin_line_id.qty_received')
    def _compute_qty_received(self):
        for record in self:
            qty_received = 0.0
            if record.origin_line_id:
                qty_received = record.origin_line_id.qty_received
            elif record.picking_id and record.picking_state == 'done':
                move_ids = record.picking_id.move_ids.filtered(lambda m: m.material_id.id == record.id)
                if move_ids:
                    qty_received = move_ids.quantity_done if len(move_ids) == 1 else move_ids[0].quantity_done
            record.qty_received = qty_received

    @api.depends("price_unit", "quantity")
    def compute_total_price(self):
        for r in self:
            r.total_price = r.price_unit * r.quantity

    @api.depends('quantity', 'cost')
    def _compute_cost_subtotal(self):
        for record in self:
            record.cost_subtotal = record.quantity * record.cost

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.cost = self.product_id.standard_price
            self.price_unit = self.product_id.list_price

    def remove_analytic_id(self):
        self.analytic_move_id.unlink()

    def change_the_sent_value(self):
        for rec in self:
            picking_type_id = False
            if rec.task_id and rec.task_id.partner_id:
                partner_id = rec.task_id.partner_id
            else:
                partner_id = rec.project_id.partner_id
            if rec.quantity < 0:
                picking_type_id = self.env.company.operation_type_entrada_id
            if rec.quantity >= 0:
                picking_type_id = self.env.company.operation_type_id
            if not picking_type_id:
                raise ValidationError(
                    _(f'No se ha definido el tipo de operacion en la compañia {self.env.company.name}. \nPor favor configure el tipo de operacion desde los ajustes de la compañia.'))
            domain = [
                ('project_id', '=', self.project_id.id),
                ('state', '=', 'draft'),
                ('picking_type_id', '=', picking_type_id.id)
            ]
            if partner_id:
                domain += [('partner_id', '=', partner_id.id)]
            else:
                domain += [('partner_id', '=', False)]

            picking_ids = self.env['stock.picking'].search(domain)
            if not picking_ids:
                stock = self.env['stock.picking'].create({
                    'partner_id': partner_id.id if partner_id else False,
                    'picking_type_id': picking_type_id.id,
                    'scheduled_date': date.today(),
                    'project_id': rec.project_id.id,
                    'move_type': 'direct',
                    'location_id': self.get_location_id(picking_type_id, partner_id),
                    'location_dest_id': self.get_location_dest_id(picking_type_id, partner_id),
                })
                rec.picking_id = stock.id
                stock.move_line_ids.create({
                    'picking_id': stock.id,
                    'product_id': rec.product_id.id,
                    'qty_done': abs(rec.quantity),
                    'product_uom_id': rec.product_id.uom_id.id,
                    'location_id': stock.location_id.id,
                    'location_dest_id': stock.location_dest_id.id,
                })
                # stock.move_line_ids.write({
                #     'product_uom_qty': abs(rec.quantity)
                # })
                stock.move_line_ids.move_id.write({
                    'product_uom_qty': abs(rec.quantity),
                    'material_id': rec.id
                })
            else:
                move_id = self.env['stock.move.line'].create({
                    'picking_id': picking_ids[0].id,
                    'product_id': rec.product_id.id,
                    'qty_done': abs(rec.quantity),
                    'product_uom_id': rec.product_id.uom_id.id,
                    'location_id': picking_ids[0].location_id.id,
                    'location_dest_id': picking_ids[0].location_dest_id.id,
                })
                rec.picking_id = picking_ids[0].id
                move_id.move_id.write({
                    'product_uom_qty': abs(rec.quantity),
                    'material_id': rec.id
                })


    def get_location_id(self, picking_type_id, partner_id):
        if picking_type_id and picking_type_id.default_location_src_id:
            return picking_type_id.default_location_src_id.id
        elif partner_id:
            return partner_id.property_stock_supplier.id
        else:
            customerloc, location_id = self.env['stock.warehouse']._get_partner_locations()
            return location_id.id

    def get_location_dest_id(self, picking_type_id, partner_id):
        if picking_type_id and picking_type_id.default_location_dest_id:
            return picking_type_id.default_location_dest_id.id
        elif partner_id:
            return partner_id.property_stock_customer.id
        else:
            location_dest_id, supplierloc = self.env['stock.warehouse']._get_partner_locations()
            return location_dest_id.id

    @api.onchange('task_id')
    def onchange_project_id(self):
        if self.task_id:
            self.project_id = self.task_id.project_id

    @api.onchange("quantity")
    def onchange_quantity(self):
        if self.quantity < 0:
            material_id = self.env['project.task.material'].search([
                ('project_id', '=', self.project_id.id),
                ('id', '!=', self._origin.id),
                ('product_id', '=', self.product_id.id)]
            )
            if abs(self.quantity) > sum(material_id.mapped('quantity')):
                raise UserError(_("No puedes retirar más cantidad de '%d'" % sum(material_id.mapped('quantity'))))

    def action_open_create_compra_wizard(self):
        return {
            'name': _('Crear compras'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'wizard.create.purchase.order',
            'target': 'new',
            'context': self._context.copy(),
        }


    def show_pickings(self):
        pickings_ids = self.env['stock.move'].search([('material_id', '=', self.id)]).mapped('picking_id')
        res = {
            'name': _('Albaranes'),
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pickings_ids.ids)],
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'context': {'create': False, 'active_test': False},
        }
        if len(pickings_ids) == 1:
            res.update(view_mode='form', res_id=pickings_ids.id)
        return res

    def unlink(self):
        if self.picking_id or self.origin_line_id:
            raise ValidationError(_('No puedes eliminar una línea de material vinculada a un pedido de compra o un albarán.'))
        return super(ProjectTaskMaterial, self).unlink()