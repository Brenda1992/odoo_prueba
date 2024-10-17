# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ProjectCertification(models.Model):
    _name = 'project.certification'
    _description = 'Certifacion'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.depends('line_ids', 'line_ids.certified', 'line_ids.price_subtotal')
    def _compute_amount_certified(self):
        for record in self:
            lines_certified = sum(record.line_ids.mapped('certified'))
            lines_subtotal = sum(record.line_ids.mapped('price_subtotal'))

            importe_certificado = lines_certified
            importe_certificado_actual = lines_certified - record.certified_before
            importe_certificado_percentage = lines_certified / lines_subtotal if lines_subtotal else 0
            importe_certificado_actual_percentage = importe_certificado_percentage - record.certified_before_ptje
            record.update({
                'importe_certificado': importe_certificado,
                'importe_certificado_actual': importe_certificado_actual,
                'importe_certificado_percentage': importe_certificado_percentage,
                'importe_certificado_actual_percentage': importe_certificado_actual_percentage
            })

    @api.depends('project_id')
    def _compute_project_certification_sequence(self):
        for record in self:
            record.sequence = 0
            project_name_same = self.env['project.certification'].search([('project_id', '=', self.project_id.id)]).mapped('sequence')
            if project_name_same:
                record.sequence = max(project_name_same) + 1

    name = fields.Char(string='Nombre', required=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date().today())
    date_signed = fields.Date(string='Fecha aceptacion cliente')
    comment = fields.Text(string='Notas')
    project_id = fields.Many2one('project.project', required=True, string='Proyecto')
    currency_id = fields.Many2one(related='project_id.analytic_account_id.currency_id', string='Moneda')
    line_ids = fields.One2many('project.certification.line', 'certification_id', string='Linea')
    capitulo_line_ids = fields.One2many('project.certification.capitulo.line', 'certification_id', string='Capitulos')
    move_id = fields.Many2one('account.move', string='Factura', readonly=True)
    state = fields.Selection([('draft', 'Borrador'), ('invoiced', 'Facturado')], string="Estado", default='draft', required=True, )
    sequence = fields.Integer(string='Num Certificación', compute='_compute_project_certification_sequence', store=True)
    certified_before = fields.Monetary(string='Importe Certificado Previo', compute='_total_certified_before')
    certified_before_ptje = fields.Float(string='% Importe Certificado Previo', compute='_total_certified_before')
    importe_certificado = fields.Monetary(string='Importe certificado', compute='_compute_amount_certified', store=False)
    importe_certificado_percentage = fields.Float(string='% Importe Certificado', compute='_compute_amount_certified', store=False)
    importe_certificado_actual = fields.Monetary(string='Importe certificado Actual', compute='_compute_amount_certified', store=False)
    importe_certificado_actual_percentage = fields.Float(string='% Importe Certificado Actual', compute='_compute_amount_certified', store=False)
    invoice_count_certification = fields.Integer(compute='compute_count')
    sale_order_count_certification = fields.Integer(compute='compute_sale_order_count')
    ultima_certificacion = fields.Boolean('Ultima Certificacion')
    partner_id = fields.Many2one('res.partner', related='project_id.partner_id', string='Cliente')
    importe_presupuestado = fields.Float(string='Importe presupuestado', compute='_total_importe_presupuestado')
    forma_pago = fields.Char(string="Forma Pago", compute="_forma_pago")
    ptje_retencion = fields.Float(string="% Retención")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    amount_text = fields.Char('Importe en Texto')

    def add_lines(self):
        # previous_record = self.env['project.certification'].search([('project_id', '=', self.project_id.id), ('id', '!=', self.id)], limit=1, order='id desc')
        # if previous_record.state == 'draft' and previous_record.project_id.name == self.line_ids.certification_id.project_id.name:
        previous_record = self.env['project.certification'].search([('project_id', '=', self.project_id.id), ('id', '!=', self.id), ('state', '=', 'draft')])
        capitulo_ids = []
        if previous_record:
            raise ValidationError(_('Error: no se puede crear una certificación de este proyecto porque existe una certificación previa sin confirmar'))

        previous_ultima_certificacion_record = self.env['project.certification'].search(
            [('project_id', '=', self.project_id.id), ('id', '!=', self._origin.id), ('ultima_certificacion', '=', True)])
        if previous_ultima_certificacion_record:
            raise ValidationError(
                _(f'La Certificación Número {previous_ultima_certificacion_record.sequence} del proyecto {previous_ultima_certificacion_record.project_id.name} ya ha sido establecida como la ultima certificación.'))

        if self.state == 'draft':
            certification_line = [
                line.project_production_line_id.id for line in self.line_ids]
            project_certification_list = []
            project_certification_capitulo_list = []
            for line in self.project_id.project_production_ids.filtered(lambda line: line.id not in certification_line):
                certified_before = 0
                certified_before_ptje = 0
                quantity_certified_before = 0
                secuencia = self.sequence - 1
                if secuencia >= 1:
                    previous_record = self.env['project.certification'].search(
                        [('project_id', '=', self.project_id.id), ('sequence', '=', secuencia)],
                        limit=1, order='id desc')
                    if previous_record.project_id == self.project_id and self.project_id:
                        previous_line = previous_record.line_ids.filtered(
                            lambda pl: pl.project_production_line_id == line)
                        if previous_line:
                            certified_before = previous_line[0].certified
                            certified_before_ptje = previous_line[0].ptje
                            quantity_certified_before = previous_line[0].quantity_certified
                project_certification_list.append({
                    'project_production_line_id': line.id,
                    'certification_id': self._origin.id,
                    'certified': certified_before,
                    'ptje': certified_before_ptje,
                    'quantity_certified': quantity_certified_before,
                })
                if not line.capitulo_id.id in capitulo_ids:
                    project_certification_capitulo_list.append({
                        'certification_id': self._origin.id,
                        'capitulo_id': line.capitulo_id.id,
                    })
                    capitulo_ids.append(line.capitulo_id.id)

            self.write({
                'line_ids': [(0, 0, values) for values in project_certification_list],
                'capitulo_line_ids': [(0, 0, values) for values in project_certification_capitulo_list]
            })

    @api.onchange('project_id')
    def _onchange_project_id(self):
        for r in self:
            r.line_ids = False
            r.capitulo_line_ids = False
            capitulo_ids =[]
            if r.project_id:
                previous_record = self.env['project.certification'].search(
                    [('project_id', '=', r.project_id.id), ('id', '!=', r._origin.id), ('state', '=', 'draft')])
                if previous_record:
                    raise ValidationError(
                        _('Error: no se puede crear una certificación de este proyecto porque existe una certificación previa sin confirmar'))

                previous_ultima_certificacion_record = self.env['project.certification'].search(
                    [('project_id', '=', r.project_id.id), ('id', '!=', r._origin.id), ('ultima_certificacion', '=', True)])
                if previous_ultima_certificacion_record:
                        raise ValidationError(
                            _(f'La Certificación Número {previous_ultima_certificacion_record.sequence} del proyecto {previous_ultima_certificacion_record.project_id.name} ya ha sido establecida como la ultima certificación.'))

                if r.state == 'draft':
                    certification_line = [
                        line.project_production_line_id.id for line in self.line_ids]
                    project_certification_list = []
                    project_certification_capitulo_list = []
                    for line in self.project_id.project_production_ids.filtered(lambda line: line.id not in certification_line):
                        certified_before = 0
                        certified_before_ptje = 0
                        quantity_certified_before = 0
                        secuencia = r.sequence - 1
                        if secuencia >= 1:
                            previous_record = self.env['project.certification'].search(
                                [('project_id', '=', r.project_id.id),
                                 ('sequence', '=', secuencia)],
                                limit=1, order='id desc')
                            if previous_record.project_id == r.project_id and r.project_id:
                                previous_line = previous_record.line_ids.filtered(
                                    lambda pl: pl.project_production_line_id == line)
                                if previous_line:
                                    certified_before = previous_line[0].certified
                                    certified_before_ptje = previous_line[0].ptje
                                    quantity_certified_before = previous_line[0].quantity_certified
                        project_certification_list.append({
                            'project_production_line_id': line.id,
                            'certification_id': r._origin.id,
                            'certified': certified_before,
                            'ptje': certified_before_ptje,
                            'quantity_certified': quantity_certified_before,
                        })

                        if not line.capitulo_id.id in capitulo_ids:
                            project_certification_capitulo_list.append({
                                'certification_id': r._origin.id,
                                'capitulo_id': line.capitulo_id.id,
                            })
                            capitulo_ids.append(line.capitulo_id.id)

                    r.update({
                        'line_ids': [(0, 0, values) for values in project_certification_list],
                        'capitulo_line_ids': [(0, 0, values) for values in project_certification_capitulo_list]
                    })

    def unlink(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(_("No se puede borrar una certificación que está facturada"))
        return super(ProjectCertification, self).unlink()


    def prepare_invoice_lines(self):
        billing_type = self.env.company.billing_type
        billing_lines = self.env.company.billing_lines
        previous_billings = self.env.company.previous_billings
        product_certificaciones_previas_id = self.env.company.product_certificaciones_previas_id
        lines = []
        if billing_type == 'current_billing':
            lines.append(
                (0, 0, {
                    'product_id': product_certificaciones_previas_id.product_variant_id.id,
                    'quantity': 1,
                    'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                    'price_unit': self.importe_certificado_actual
                })
            )
        elif billing_type == 'origin_billing':
            lines.append(
                (0, 0, {
                    'product_id': product_certificaciones_previas_id.product_variant_id.id,
                    'quantity': 1,
                    'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                    'price_unit': self.importe_certificado
                })
            )
        elif billing_type == 'part_billing' and billing_lines == 'all':
            for line in self.line_ids:
                lines.append(
                    (0, 0, {
                        'product_id': line.sale_line_id.product_id.id,
                        'name': line.name,
                        'quantity': line.quantity_certified,
                        'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                        'price_unit': line.price_subtotal
                    })
                )
        elif billing_type == 'part_billing' and billing_lines == 'cert_lines':
            line_ids = self.line_ids.filtered(lambda l: l.quantity_certified > 0 and l.price_subtotal > 0)
            for line in line_ids:
                lines.append(
                    (0, 0, {
                        'product_id': line.sale_line_id.product_id.id,
                        'name': line.name,
                        'quantity': line.quantity_certified,
                        'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                        'price_unit': line.price_subtotal
                    })
                )
        # Facturas certificaciones anteriores
        if previous_billings == 'all':
            invoice_previous_certification_ids = self.env['project.certification'].search([
                ('project_id', '=', self.project_id.id),
                ('state', '=', 'invoiced')
            ], order='id desc').mapped('move_id')
            for invoice in invoice_previous_certification_ids:
                name = invoice.name
                invoice_date = ' / ' + str(invoice.invoice_date) if invoice.invoice_date else ''
                lines.append(
                    (0, 0, {
                        'product_id': product_certificaciones_previas_id.product_variant_id.id,
                        'name': 'Certificaciones anteriores / Factura: ' + name + invoice_date,
                        'quantity': 1,
                        'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                        'price_unit': invoice.amount_untaxed * -1 if invoice.amount_untaxed > 0 else invoice.amount_untaxed
                    })
                )
        elif previous_billings == 'unique_line' and self.certified_before > 0:
            lines.append(
                (0, 0, {
                    'product_id': product_certificaciones_previas_id.product_variant_id.id,
                    'name': 'Certificaciones previas',
                    'quantity': 1,
                    'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                    'price_unit': self.certified_before * -1 if self.certified_before > 0 else self.certified_before
                })
            )
        return lines

    def prepare_invoice(self):
        invoice_data = {
            'partner_id': self.project_id.partner_id.id if self.project_id.partner_id else False,
            'move_type': 'out_invoice',
            'project_id': self.project_id.id,
            'certification_id': self.id,
            'invoice_line_ids': self.prepare_invoice_lines()
        }
        return invoice_data

    def create_invoice(self):
        product_retenciones_id = self.env.company.product_retenciones_id
        if product_retenciones_id:
            if not product_retenciones_id.property_account_income_id:
                raise ValidationError("Error: debe configurar una cuenta contable en el producto de retenciones.")
        else:
            raise ValidationError("Error: debe configurar un producto para las retenciones en la ficha de la compañía.")

        if self.line_ids:
            billing_type = self.env.company.billing_type
            invoice = self.env['account.move'].create(self.prepare_invoice())
            if invoice:
                self.write({
                    'state': 'invoiced',
                    'move_id': invoice.id
                })

                if billing_type == 'current_billing' and self.ptje_retencion > 0:
                    price_unit = invoice.amount_untaxed * (self.ptje_retencion/100)
                    invoice.write({
                        'invoice_line_ids': [(0, 0, {
                            'product_id': product_retenciones_id.product_variant_id.id,
                            'quantity': 1,
                            'account_id': product_retenciones_id.property_account_income_id.id,
                            'analytic_distribution': {self.project_id.analytic_account_id.id: 100},
                            'price_unit': (price_unit * -1) if price_unit > 0 else price_unit,
                            'tax_ids': [(6, 0, product_retenciones_id.taxes_id.ids)]
                        })]
                    })

    # def create_lines_invoice(self):
    #     account_id = self.env.company.product_certificaciones_previas_id.property_account_income_id if self.env.company.product_certificaciones_previas_id.property_account_income_id else self.env.company.product_certificaciones_previas_id.categ_id.property_account_income_categ_id
    #
    #     # if not account_id and not self.ultima_certificacion:
    #     #     raise ValidationError(_(f'No se ha seleccionado la Cuenta de certificaciones en la compañía {self.env.company.name}. \nPor favor configure la Cuenta de certificaciones desde los ajustes de la compañia.'))
    #     lines = []
    #     for line in self.line_ids.filtered(lambda l: l.quantity_certified):
    #         price_unit = line.certified/line.quantity_certified if line.quantity_certified else 0
    #         values = {
    #             'product_id': line.sale_line_id and line.sale_line_id.product_id.id or False,
    #             'name': line.name,
    #             'quantity': line.quantity_certified,
    #             'analytic_account_id': self.project_id.analytic_account_id.id,
    #             'price_unit': price_unit,
    #             'price_subtotal': line.certified,
    #         }
    #         if account_id:
    #             values.update({'account_id': account_id,})
    #         if line.sale_line_id:
    #             values.update({'sale_line_ids': [(4, line.sale_line_id.id)]})
    #         lines.append((0, 0, values))
    #     if self.sequence > 1:
    #         product_certificaciones_previas_id = self.env.company.product_certificaciones_previas_id
    #         if not product_certificaciones_previas_id:
    #             raise ValidationError(_(f'No se ha seleccionado producto de certificaciones previas en la compañía {self.env.company.name}. \nPor favor configure el producto de certificaciones previas desde los ajustes de la compañia.'))
    #         else:
    #             if self.ultima_certificacion:
    #                 lines.append((0, 0, {'product_id': product_certificaciones_previas_id.product_variant_id.id,
    #                                      'quantity': 1,
    #                                      'analytic_account_id': self.project_id.analytic_account_id.id,
    #                                      'price_unit': -line.certified_before,
    #                                      'price_subtotal': -line.certified_before
    #                                      }))
    #             else:
    #                 lines.append((0, 0, {'product_id': product_certificaciones_previas_id.product_variant_id.id,
    #                                      'quantity': 1,
    #                                      'account_id': account_id,
    #                                      'analytic_account_id': self.project_id.analytic_account_id.id,
    #                                      'price_unit': -line.certified_before,
    #                                      'price_subtotal': -line.certified_before
    #                                      }))
    #     return lines

    @api.depends('project_id')
    def _total_certified_before(self):
        for rec in self:
            secuencia = rec.sequence - 1
            certified_before = 0
            certified_before_ptje = 0
            if secuencia >= 1:
                previous_record = self.env['project.certification'].search(
                    [('project_id', '=', rec.project_id.id), ('sequence', '=', secuencia)], limit=1,
                    order='id desc')
                if previous_record.project_id == rec.project_id:
                    certified_before = previous_record.importe_certificado
                    certified_before_ptje = previous_record.importe_certificado_percentage

            rec.certified_before = certified_before
            rec.certified_before_ptje = certified_before_ptje

    def action_send_email(self):
        '''
        This function opens a window to compose an email, with the emai template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        template_id = self.env.ref('indaws_inbuilt.certificate_email_templatess')
        # try:
        #     compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        # except ValueError:
        compose_form_id = False
        template = self.env['mail.template'].browse(template_id.id)
        ctx = {
            'default_model': 'project.certification',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template),
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
            'force_email': True,
        }
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': 'Invoices',
            'view_mode': 'form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'res_id': self.move_id.id,
        }

    def action_view_sale_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        sale_orders = self.env['sale.order'].search([('project_id', '=', self.project_id.id)])
        action['domain'] = [('id', 'in', sale_orders.ids)]
        return action

    def compute_count(self):
        for record in self:
            record.invoice_count_certification = self.env['account.move'].search_count([('certification_id', '=', self.id)])

    def compute_sale_order_count(self):
        for record in self:
            record.sale_order_count_certification = self.env['sale.order'].search_count([('project_id', '=', record.project_id.id)])

    @api.onchange('ultima_certificacion')
    def _onchange_ultima_certificacion(self):
        if self.ultima_certificacion:
            certification_ids = self.env['project.certification'].search([('project_id', '=', self.project_id.id), ('ultima_certificacion', '=', True)])
            if certification_ids:
                raise ValidationError(_(f'La Certificación Número {certification_ids.sequence} del proyecto {certification_ids.project_id.name} ya ha sido establecida como la ultima certificación.'))

    @api.depends('line_ids')
    def _total_importe_presupuestado(self):
        for item in self:
            if item.line_ids:
                item.importe_presupuestado = sum(line.price_subtotal for line in item.line_ids)
            else:
                item.importe_presupuestado = 0

    @api.depends('partner_id')
    def _forma_pago(self):
        for item in self:
            item.forma_pago = item.partner_id.sale_order_ids.payment_term_id.name

    def get_capitulo_id_name(self):
        # capitulos = self.line_ids.mapped('capitulo_id')
        # capitulo_ids = self.env['sale.capitulo'].browse(capitulos)
        return self.line_ids.mapped('capitulo_id')

    def get_lines_from_capitulo(self, capitulo_id=False):
        return self.env['project.certification.line'].search([('capitulo_id','=',capitulo_id),('certification_id','=', self.id)])

    def action_view_certification_line(self):
        self.ensure_one()
        action = self.env.ref("indaws_inbuilt.action_project_certification_line").read()[0]
        action["domain"] = [("certification_id", "=", self.id)]
        # action["context"]['default_certification_id'] = self.id
        return action
