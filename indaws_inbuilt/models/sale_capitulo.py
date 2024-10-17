# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleCapitulo(models.Model):
    _name = 'sale.capitulo'
    _description = 'Capitulo'

    code = fields.Char(string='Código', copy=True)
    name = fields.Char(string='Nombre', required=True)
    comment = fields.Text(string="Notas")
    order_id = fields.Many2one('sale.order', string='Presupuesto/Pedido', ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', related="order_id.company_id")
    currency_id = fields.Many2one(related="order_id.currency_id", string="Moneda")
    project_id = fields.Many2one('project.project', related='order_id.project_id', store=True)
    line_ids = fields.One2many('sale.order.line', 'capitulo_id', string='Partidas')
    price_subtotal = fields.Monetary(string='Precio de Venta', compute='_get_price_subtotal')
    cost_price = fields.Monetary(string='Precio de Coste', compute='_get_cost_price')
    product_id = fields.Many2one('product.product', string='Producto por defecto')
    task_id = fields.Many2one('project.task', string="Tarea")
    subchapter_ids = fields.One2many('sale.subchapter', 'chapter_id', string='Subchapter')

    @api.depends('line_ids')
    def _get_price_subtotal(self):
        for record in self:
            price = 0
            for line in record.line_ids:
                price += line.price_subtotal
            record.price_subtotal = price

    @api.depends('line_ids')
    def _get_cost_price(self):
        for record in self:
            cost = 0
            for line in record.line_ids:
                cost += line.cost_subtotal
            record.cost_price = cost

    def modify_args(self, args, order_id):
        # Recorremos cada elemento de la lista args
        for elemento in args:
            # Verificamos si es una lista y si el primer elemento es 'order_id'
            if isinstance(elemento, list) and elemento[0] == 'order_id':
                elemento[2] = [order_id]
                return args
        # Si no se encuentra 'order_id', podemos agregar un nuevo elemento.
        args.append(['order_id', 'in', [order_id]])
        return args

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('order_id'):
            args = self.modify_args(args, self._context.get('order_id'))
        return super(SaleCapitulo, self)._search(
            args, offset=offset, limit=limit,
            order=order, count=count,
            access_rights_uid=access_rights_uid
        )

    def name_get(self):
        res = []
        for record in self:
            name = record.name
            if record.code and record.code != '':
                name = record.code + ' - ' + name
            res.append((record.id, name))
        return res

    def unlink(self):
        cont = 1
        for line in self.order_id.sale_capitule_line:
            if line.id not in self.ids:
                line.write({'code': str(cont).zfill(2) if (cont < 10) else str(cont)})
                cont += 1
        return super(SaleCapitulo, self).unlink()