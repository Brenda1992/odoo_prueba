# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    code = fields.Char(string='Código', copy=True)
    capitulo_id = fields.Many2one('sale.capitulo', string='Capitulo', ondelete='restrict', copy=True)
    price_type = fields.Selection([
        ('automático', 'Automático'),
        ('manual', 'Manual')
    ],
        string='Tipo de Precio',
        default='manual',
        copy=True
    )
    unidades_ids = fields.One2many('sale.unidad.obra', 'order_line_id', string='Unidades de Obra', copy=True)
    cost_subtotal = fields.Monetary(string='Precio de coste', compute='_get_cost_subtotal')
    incremento = fields.Float(string='% incremento', copy=True)
    order_id_domain = fields.Many2many(comodel_name='sale.order')
    unidades_count = fields.Integer()
    order_pricelist_id = fields.Many2one('product.pricelist', related="order_id.pricelist_id", string='Pricelist')
    long_description = fields.Text(string='Descripción Larga')
    measurement_ids = fields.One2many('sale.measurement', 'order_line_id', string='Mediciones', copy=True)
    total_measurement = fields.Float('Cantidad Total', compute='_compute_total_measurement', digits=(16, 3))
    subchapter_id = fields.Many2one(comodel_name='sale.subchapter', string="Subchapter")
    import_bc3 = fields.Boolean(string='Importado bc3', default=False)

    @api.onchange('capitulo_id')
    def _onchange_capitulo(self):
        active_id = False
        if self._context.get('active_id'):
            active_id = self._context.get('active_id')
        elif self._context.get('params'):
            active_id = self._context.get('params').get('id')
        if active_id:
            order_id = self.env['sale.order'].browse(active_id)
            if order_id:
                domain = [('order_id', 'in', order_id.ids)]
        elif self.order_id._origin:
            domain = [('order_id', '=', self.order_id._origin.id)]
        else:
            domain = [('id', '=', 0)]
        return {'domain': {'capitulo_id': domain}}

    @api.onchange('incremento')
    def price_unit_change(self):
        for rec in self.unidades_ids:
            # if rec.product_type_calc != 'mano_de_obra':
            if not rec.product_type_calc.is_part_hours:
                rec.write({'incremento': self.incremento})
                rec.onchange_incremento()
            else:
                rec.write({'incremento': rec.incremento})
        self.onchage_unidades_ids()

    @api.model
    def default_get(self, vals):
        res = super(SaleOrderLine, self).default_get(vals)
        if self._context.get('active_model', False) == 'sale.order' and self._context.get('active_id', False):
            ctx = self._context.get('active_id', False)
            order = self.env['sale.order'].browse(ctx)
            order_lines = len([line for line in order.order_line])
            res.update({
                'code': str('%03d' % (order_lines + 1)),
                'order_id_domain':[(6,0,order.ids)]
            })
        return res

    @api.depends('purchase_price', 'product_uom_qty')
    def _get_cost_subtotal(self):
        for record in self:
            record.cost_subtotal =record.purchase_price*record.product_uom_qty

    @api.model_create_multi
    def create(self, vals):
        lines = super(SaleOrderLine, self).create(vals)
        for rec in lines:
            if rec.capitulo_id and rec.capitulo_id.id not in rec.order_id.sale_capitule_line.ids:
                sale_capitule_line = self.env['sale.capitulo'].search([
                    ('name', '=', rec.capitulo_id.name),
                    # ('bc3_import_id', '=', rec.capitulo_id.bc3_import_id),
                    ('order_id', '=', rec.order_id.id)
                ])
                if not sale_capitule_line:
                    sale_capitule_line = self.env['sale.capitulo'].create({
                        'name': rec.capitulo_id.name,
                        'order_id': rec.order_id.id,
                        # 'bc3_import_id': rec.capitulo_id.bc3_import_id
                    })
                rec.capitulo_id = sale_capitule_line
            if rec.product_id and not rec.unidades_ids:
                unidades_ids_list = []
                rec.unidades_ids = [(5,)]
                for line in rec.product_id.unidades_ids:
                    unidades_ids_list.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_type_calc': line.product_type_calc.id,
                        'quantity': line.quantity,
                        'cost_unit': line.cost_unit,
                        'incremento': line.incremento,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                        'cost_subtotal': line.cost_subtotal,
                        'uom_id': line.uom_id.id,
                        'comment': line.comment,
                        'order_line_id': rec.id,
                        'order_id': rec.order_id.id
                    }))
                rec.unidades_ids = unidades_ids_list
                rec.price_type = rec.product_id.price_type
            if rec.order_id.project_id and rec.order_id.state in ['sale', 'done']:
                self.env['project.production'].create({
                    'project_id': rec.order_id.project_id.id,
                    'sale_line_id': rec.id,
                    'name': rec.name,
                    'capitulo_id': rec.capitulo_id.id,
                    'quantity': rec.product_uom_qty,
                    'price_subtotal': rec.price_subtotal,
                    'task_id': rec.task_id.id
                })
        lines.order_id._update_code_capitulos() if len(lines) == 1 else lines[0].order_id._update_code_capitulos()
        return lines

    def write(self, values):
        result = super(SaleOrderLine, self).write(values)
        for rec in self:
            if 'capitulo_id' in values and values['capitulo_id'] not in rec.order_id.sale_capitule_line.ids:
                rec.order_id.sale_capitule_line = [(4, values['capitulo_id'])]
            if 'product_id' in values:
                unidades_ids_list = []
                product_id = self.env['product.product'].browse(values['product_id'])
                rec.unidades_ids = [(5,)]
                for line in product_id.unidades_ids:
                    unidades_ids_list.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_type_calc': line.product_type_calc.id,
                        'quantity': line.quantity,
                        'cost_unit': line.cost_unit,
                        'incremento': line.incremento,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                        'cost_subtotal': line.cost_subtotal,
                        'uom_id': line.uom_id.id,
                        'comment': line.comment,
                        'order_line_id': self.id,
                        'order_id': self.order_id.id
                    }))
                rec.unidades_ids = unidades_ids_list
        return result

    @api.onchange('unidades_ids', 'price_type',)
    def onchage_unidades_ids(self):
        for record in self:
            #El costo siempre es automatico pero se desaparece si la linea aun no se ha guardado
            if record.price_type == 'automático' and record.unidades_ids:
                record.price_unit = sum(line['price_subtotal'] for line in record.unidades_ids)
                record.purchase_price = sum(line['cost_subtotal'] for line in record.unidades_ids)
            else:
                if not record.product_id:
                    record.price_unit = 0.0
                    record.purchase_price = 0.0
                    continue
                record.price_unit = record.product_id._get_tax_included_unit_price(
                    record.company_id or record.order_id.company_id,
                    record.order_id.currency_id,
                    record.order_id.date_order,
                    'sale',
                    fiscal_position=record.order_id.fiscal_position_id,
                    # product_price_unit=record._get_display_price(record.product_id),
                    product_price_unit=record._get_display_price(),
                    product_currency=record.order_id.currency_id
                )
                record.purchase_price = record.product_id.standard_price

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        self.onchage_unidades_ids()

    def open_sale_order_form_view(self):
        return {
            'name': 'Edit Order Line',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
            'view_id': self.env.ref('indaws_inbuilt.sale_order_line_view_form_indaws').id
        }


    @api.onchange('name', 'product_uom_qty', 'price_subtotal')
    def _onchange_order_line(self):
        if self.order_id.project_id and self.name:
            project_production_id = self.env['project.production'].search([
                ('sale_line_id', '=', self.id or self._origin.id)
            ])
            if project_production_id:
                project_production_id.write({
                    'name': self.name,
                    'quantity': self.product_uom_qty,
                    'price_subtotal': self.price_subtotal
                })

    def unlink(self):
        for rec in self:
            project_production_id = self.env['project.production'].search([('sale_line_id', '=', rec.id)])
            if project_production_id:
                project_production_id.unlink()
            rec.order_id._update_code_lines(rec.ids)
        return super(SaleOrderLine, self).unlink()

    @api.onchange('product_id')
    def _onchange_product_id_warning(self):
        res = super(SaleOrderLine, self)._onchange_product_id_warning()
        self.unidades_ids = [(5,)]
        if self.product_id and self.product_id.unidades_ids:
            unidades_ids_list = []
            for line in self.product_id.unidades_ids:
                unidades_ids_list.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_type_calc': line.product_type_calc.id,
                    'quantity': line.quantity,
                    'cost_unit': line.cost_unit,
                    'incremento': line.incremento,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                    'cost_subtotal': line.cost_subtotal,
                    'uom_id': line.uom_id.id,
                    'comment': line.comment
                }))
            self.unidades_ids = unidades_ids_list
            self.price_type = self.product_id.price_type
            if self.product_id.price_type == 'automático':
                self.price_unit = self.product_id.computed_sale_price
            else:
                self.price_unit = self.product_id.list_price
        return res

    def name_get(self):
        res = []
        for record in self:
            name = record.name
            if record.code and record.code != '':
                name = record.code + ' - ' + name
            res.append((record.id, name))
        return res

    @api.depends('measurement_ids')
    def _compute_total_measurement(self):
        for record in self:
            total_measurement = sum(record.measurement_ids.mapped('partial'))
            update_data = {'total_measurement': total_measurement}
            if total_measurement > 0 and not record.import_bc3:
                update_data.update(product_uom_qty=total_measurement)
            record.write(update_data)
