# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import os
import frappe
from frappe.model.document import Document
from frappe.utils.password import encrypt

class S3FileAttachment(Document):
    @property
    def aws_key(self):
        return os.environ.get("S3_KEY", self.get_db_value('aws_key'))

    @property
    def aws_secret(self):
        if os.environ.get("S3_SECRET"):
            return encrypt(os.environ.get("S3_SECRET"))
        else:
            return self.get_db_value('aws_secret')

    @property
    def bucket_name(self):
        return os.environ.get("S3_BUCKET_NAME", self.get_db_value('bucket_name'))

    @property
    def delete_file_from_cloud(self):
        return int(os.environ.get("S3_DELETE_FROM_CLOUD", self.get_db_value('delete_file_from_cloud')))

    @property
    def region_name(self):
        return os.environ.get("S3_REGION_NAME", self.get_db_value('region_name'))

    @property
    def signed_url_expiry_time(self):
        return int(os.environ.get("S3_SIGNED_URL_EXPIRY_TIME", self.get_db_value('signed_url_expiry_time')))

    def as_dict(self, no_nulls=False, no_default_fields=False, convert_dates_to_str=False):
        doc = super(S3FileAttachment, self).as_dict(no_nulls=no_nulls)
        doc["aws_key"] = self.aws_key
        doc["aws_secret"] = self.aws_secret
        doc["bucket_name"] = self.bucket_name
        doc["delete_file_from_cloud"] = self.delete_file_from_cloud
        doc["region_name"] = self.region_name
        doc["signed_url_expiry_time"] = self.signed_url_expiry_time
        return doc
