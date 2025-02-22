import frappe
from frappe_s3_attachment.controller import upload_voucher_pdf_to_s3
from frappe.utils import today

def execute():
    import frappe
    from frappe_s3_attachment.controller import upload_voucher_pdf_to_s3
    s3_settings_doc = frappe.get_doc('S3 File Attachment', 'S3 File Attachment')
    if s3_settings_doc.aws_key and s3_settings_doc.aws_secret:
        filters = frappe._dict({'docstatus': 1, 'is_opening': 'No', 'voucher_pdf_link': ('is', 'not set'), 'posting_date': ["Between", ['2021-10-01', today()]]})
        print_format = frappe.get_meta("Sales Invoice").default_print_format
        if frappe.db.get_default("country") == 'India':
            enable_e_invoice = frappe.db.get_value("E Invoice Settings", "E Invoice Settings", "enable_e_invoice")
            if enable_e_invoice:
                filters['einvoice_status'] = ('!=', 'Pending')
        
        for voucher in frappe.get_all('Sales Invoice', fields=['name', "'Sales Invoice' as doctype", 'posting_date', 'voucher_pdf_link'], filters=filters, order_by="creation desc", limit=500):
            voucher_pdf_link = upload_voucher_pdf_to_s3(voucher, print_format, is_private=1)
            frappe.db.sql(""" update `tabSales Invoice` set voucher_pdf_link=%s where name=%s""", (voucher_pdf_link, voucher.name), auto_commit=1)