from __future__ import unicode_literals

import random
import string
import datetime
import re
import os

import boto3
import magic
import frappe
from frappe.utils.pdf import cleanup
from PyPDF2 import PdfFileWriter, PdfFileReader
from six import string_types
import io

from botocore.exceptions import ClientError


class S3Operations(object):

    def __init__(self):
        """
        Function to initialise the aws settings from frappe S3 File attachment
        doctype.
        """
        self.s3_settings_doc = frappe.get_doc(
            'S3 File Attachment',
            'S3 File Attachment',
        )
        self.aws_key = self.s3_settings_doc.aws_key
        self.aws_secret = self.s3_settings_doc.get_password('aws_secret')
        if (
            self.aws_key and
            self.aws_secret
        ):
            self.S3_CLIENT = boto3.client(
                's3',
                aws_access_key_id=self.aws_key,
                aws_secret_access_key=self.aws_secret,
                region_name=self.s3_settings_doc.region_name,
            )
        else:
            self.S3_CLIENT = boto3.client('s3')
        self.BUCKET = self.s3_settings_doc.bucket_name
        self.folder_name = self.s3_settings_doc.folder_name

    def key_generator(self, file_name, parent_doctype, parent_name):
        """
        Generate keys for s3 objects uploaded with file name attached.
        """
        file_name = file_name.replace(' ', '_')
        file_name = strip_special_chars(file_name)
        key = ''.join(
            random.choice(
                string.ascii_uppercase + string.digits) for _ in range(8)
        )

        today = datetime.datetime.now()
        year = today.strftime("%Y")
        month = today.strftime("%m")
        day = today.strftime("%d")

        doc_path = None

        try:
            doc_path = frappe.db.get_value(
                parent_doctype,
                filters={'name': parent_name},
                fieldname=['s3_folder_path']
            )
            doc_path = doc_path.rstrip('/').lstrip('/')
        except Exception as e:
            print(e)

        if not doc_path:
            if self.folder_name:
                if parent_doctype:
                    final_key = self.folder_name + "/" + year + "/" + month + \
                        "/" + day + "/" + parent_doctype + "/" + key + "_" + \
                        file_name
                else:
                    final_key = self.folder_name + "/" + year + "/" + month + \
                                "/" + day + "/" + key + "_" + \
                                file_name
            else:
                final_key = year + "/" + month + "/" + day + "/" + \
                    parent_doctype + "/" + key + "_" + file_name
            return final_key
        else:
            final_key = doc_path + '/' + key + "_" + file_name
            return final_key

    def upload_files_to_s3_with_key(
            self, file_path, file_name, is_private, parent_doctype, parent_name, file_key=None
    ):
        """
        Uploads a new file to S3.
        Strips the file extension to set the content_type in metadata.
        """
        mime_type = magic.from_file(file_path, mime=True)
        key = file_key if file_key else self.key_generator(file_name, parent_doctype, parent_name)
        content_type = mime_type
        try:
            if is_private:
                self.S3_CLIENT.upload_file(
                    file_path, self.BUCKET, key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "Metadata": {
                            "ContentType": content_type,
                            "file_name": file_name
                        }
                    }
                )
            else:
                self.S3_CLIENT.upload_file(
                    file_path, self.BUCKET, key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "ACL": 'public-read',
                        "Metadata": {
                            "ContentType": content_type,

                        }
                    }
                )

        except boto3.exceptions.S3UploadFailedError:
            frappe.throw(frappe._("File Upload Failed. Please try again."))
        return key

    def delete_from_s3(self, key):
        """Delete file from s3"""
        self.s3_settings_doc = frappe.get_doc(
            'S3 File Attachment',
            'S3 File Attachment',
        )

        if self.s3_settings_doc.delete_file_from_cloud:
            S3_CLIENT = boto3.client(
                's3',
                aws_access_key_id=self.aws_key,
                aws_secret_access_key=self.aws_secret,
                region_name=self.s3_settings_doc.region_name,
            )

            try:
                S3_CLIENT.delete_object(
                    Bucket=self.s3_settings_doc.bucket_name,
                    Key=key
                )
            except ClientError:
                frappe.throw(frappe._("Access denied: Could not delete file"))

    def read_file_from_s3(self, key):
        """
        Function to read file from a s3 file.
        """
        return self.S3_CLIENT.get_object(Bucket=self.BUCKET, Key=key)

    def get_url(self, key):
        """
        Return url.

        :param bucket: s3 bucket name
        :param key: s3 object key
        """
        if self.s3_settings_doc.signed_url_expiry_time:
            self.signed_url_expiry_time = self.s3_settings_doc.signed_url_expiry_time # noqa
        else:
            self.signed_url_expiry_time = 120

        url = self.S3_CLIENT.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.BUCKET, 'Key': key},
            ExpiresIn=self.signed_url_expiry_time
        )

        return url

def strip_special_chars(file_name):
    """
    Strips file charachters which doesnt match the regex.
    """
    regex = re.compile('[^0-9a-zA-Z._-]')
    file_name = regex.sub('', file_name)
    return file_name

def generate_voucher_pdf_key(voucher_doctype, posting_date, folder_name, file_name):
    file_name = strip_special_chars(file_name.replace(' ', '_').replace('tmp', ''))
    # today = datetime.datetime.now()
    if isinstance(posting_date, string_types):
       posting_date = datetime.datetime.strptime(posting_date, '%Y-%m-%d')
    year = posting_date.strftime("%Y")
    month = posting_date.strftime("%m")
    return folder_name + "/" + year + "/" + month + "/" + voucher_doctype.replace(' ', '_') + "/" + file_name

def get_voucher_file_details(voucher_doc):
    file_name = "{0}.pdf".format(voucher_doc.name)
    file_name = file_name.replace(' ', '').replace('/', '-')
    file_path = os.path.join("/", "tmp", file_name)
    return file_name, file_path

def upload_voucher_pdf_to_s3(voucher_doc, print_format, is_private=1):
    try:
        s3_upload = S3Operations()
        if s3_upload and not (s3_upload.aws_key and s3_upload.aws_secret):
            return

        filedata = frappe.get_print(voucher_doc.doctype, voucher_doc.name, print_format, as_pdf=True)
        file_name, file_path = get_voucher_file_details(voucher_doc)

        output = PdfFileWriter()
        reader = PdfFileReader(io.BytesIO(filedata))
        output.appendPagesFromReader(reader)
        output.write(open(file_path,"wb"))

        key = generate_voucher_pdf_key(voucher_doc.doctype, voucher_doc.posting_date, s3_upload.folder_name, file_path)
        s3_upload.upload_files_to_s3_with_key(
            file_path, file_name,
            is_private, voucher_doc.doctype,
            voucher_doc.name, key
        )

        if is_private:
            method = "frappe_s3_attachment.controller.generate_file"
            file_url = """/api/method/{0}?key={1}""".format(method, key)
        else:
            file_url = '{}/{}/{}'.format(
                s3_upload.S3_CLIENT.meta.endpoint_url,
                s3_upload.BUCKET,
                key
            )
        return file_url

    except IOError as e:
            frappe.log_error('Error in uploading voucher pdf for {} '.format(voucher_doc.name))
    finally:
        cleanup(file_path,{})

def delete_voucher_pdf_from_s3(voucher_doc):
    """Delete file from s3"""
    s3 = S3Operations()
    file_name, file_path = get_voucher_file_details(voucher_doc)
    content_hash = generate_voucher_pdf_key(voucher_doc.doctype, voucher_doc.posting_date, s3.folder_name, file_path)
    if content_hash:
        s3.delete_from_s3(content_hash)


@frappe.whitelist()
def file_upload_to_s3(doc, method):
    """
    check and upload files to s3. the path check and
    """
    s3_upload = S3Operations()
    path = doc.file_url
    if path.startswith('https://s3.') or path.startswith('/api/method/frappe_s3_attachment.controller.generate_file?'):
        return
    if s3_upload and not (s3_upload.aws_key and s3_upload.aws_secret):
        return
    site_path = frappe.utils.get_site_path()
    parent_doctype = doc.attached_to_doctype
    parent_name = doc.attached_to_name
    if parent_doctype not in ["Data Import", "Prepared Report", "Digital Signature Settings"]:
        if not doc.is_private:
            file_path = site_path + '/public' + path
        else:
            file_path = site_path + path
        key = s3_upload.upload_files_to_s3_with_key(
            file_path, doc.file_name,
            doc.is_private, parent_doctype,
            parent_name
        )

        if doc.is_private:
            method = "frappe_s3_attachment.controller.generate_file"
            file_url = """/api/method/{0}?key={1}""".format(method, key)
        else:
            file_url = '{}/{}/{}'.format(
                s3_upload.S3_CLIENT.meta.endpoint_url,
                s3_upload.BUCKET,
                key
            )
        os.remove(file_path)
        doc = frappe.db.sql("""UPDATE `tabFile` SET file_url=%s, folder=%s,
            old_parent=%s, content_hash=%s WHERE name=%s""", (
            file_url, 'Home/Attachments', 'Home/Attachments', key, doc.name))
        frappe.db.commit()


@frappe.whitelist()
def generate_file(key=None):
    """
    Function to stream file from s3.
    """
    if key:
        s3_upload = S3Operations()
        signed_url = s3_upload.get_url(key)
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = signed_url
    else:
        frappe.local.response['body'] = "Key not found."
    return


def upload_existing_files_s3(name, file_name):
    """
    Function to upload all existing files.
    """
    file_doc_name = frappe.db.get_value('File', {'name': name})
    if file_doc_name:
        doc = frappe.get_doc('File', name)
        s3_upload = S3Operations()
        path = doc.file_url
        site_path = frappe.utils.get_site_path()
        parent_doctype = doc.attached_to_doctype
        parent_name = doc.attached_to_name
        if not doc.is_private:
            file_path = site_path + '/public' + path
        else:
            file_path = site_path + path
        key = s3_upload.upload_files_to_s3_with_key(
            file_path, doc.file_name,
            doc.is_private, parent_doctype,
            parent_name
        )

        if doc.is_private:
            method = "frappe_s3_attachment.controller.generate_file"
            file_url = """/api/method/{0}?key={1}""".format(method, key)
        else:
            file_url = '{}/{}/{}'.format(
                s3_upload.S3_CLIENT.meta.endpoint_url,
                s3_upload.BUCKET,
                key
            )
        os.remove(file_path)
        doc = frappe.db.sql("""UPDATE `tabFile` SET file_url=%s, folder=%s,
            old_parent=%s, content_hash=%s WHERE name=%s""", (
            file_url, 'Home/Attachments', 'Home/Attachments', key, doc.name))
        frappe.db.commit()
    else:
        pass


def s3_file_regex_match(file_url):
    """
    Match the public file regex match.
    """
    return re.match(
        r'^(https:|/api/method/frappe_s3_attachment.controller.generate_file)',
        file_url
    )


@frappe.whitelist()
def migrate_existing_files():
    """
    Function to migrate the existing files to s3.
    """
    # get_all_files_from_public_folder_and_upload_to_s3
    files_list = frappe.db.get_all('File',
                                   filters={'attached_to_doctype': ['not in', ["Data Import", "Prepared Report"]]},
                                   fields=['name', 'file_url', 'file_name'])
    for file in files_list:
        if file['file_url']:
            if not s3_file_regex_match(file['file_url']):
                upload_existing_files_s3(file['name'], file['file_name'])
    return True


def delete_from_cloud(doc, method):
    """Delete file from s3"""
    s3 = S3Operations()
    if doc.content_hash:
        s3.delete_from_s3(doc.content_hash)


@frappe.whitelist()
def ping():
    """
    Test function to check if api function work.
    """
    return "pong"

def read_from_s3(fname, file_path):
    file_details = frappe.db.sql(
        """select file_name, file_url, content_hash, is_private from `tabFile` where name=%s or file_name=%s""",
        (fname, fname), as_dict=1)
    if file_details:
        file_details = file_details[0]
        s3_upload = S3Operations()
        if file_details.is_private:
            file_path = file_path.replace(
                '/api/method/frappe_s3_attachment.controller.generate_file?key=', '')
            return [file_details.file_name,
                    s3_upload.read_file_from_s3(file_path).get("Body").read()]
        else:
            return [file_details.file_name,
                    s3_upload.read_file_from_s3(file_details.content_hash).get("Body").read()]
    else:
        frappe.throw("File not found")
