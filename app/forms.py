import os
import re
from datetime import datetime
from time import time

from api import get_event, push_event
from config import (
    ALLOWED_FILETYPES,
    EVENT_COOLDOWN,
    IMG_PATH,
    LOG_PATH,
    MAX_FILE_SIZE,
    MAX_POST_LENGTH,
    MAX_POST_ROWS,
    MIN_POST_LENGTH,
    REPORTS,
)
from flask import current_app, flash
from flask_wtf import FlaskForm
from utils import get_ip_from_request, get_new_uid, get_username, make_img_from_request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from wtforms import (
    Form,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
    validators,
)


class FeedbackForm(FlaskForm):
    subject = StringField(
        label='Subject',
        validators=[validators.Length(min=1, max=64), validators.InputRequired()],
    )
    message = TextAreaField(
        label='Message',
        validators=[
            validators.Length(min=MIN_POST_LENGTH, max=MAX_POST_LENGTH),
            validators.InputRequired(),
        ],
        id='feedback_form_message_id',
    )


class ReportForm(FlaskForm):
    category = SelectField(label='Category', choices=[(r, r) for r in REPORTS])
    message = TextAreaField(
        label='Report',
        validators=[
            validators.Length(max=MAX_POST_LENGTH),
        ],
        id='report_form_message_id',
    )


class LoginForm(FlaskForm):
    username = StringField(
        label='Username',
        validators=[validators.Length(min=1, max=32), validators.InputRequired()],
    )
    password = PasswordField(label='Password', validators=[validators.InputRequired()])


class PostCompiler:
    def __init__(
        self,
        request,
        form_text_name=None,
        form_img_name=None,
        require_text=True,
        validate_text=True,
        require_img=True,
    ):
        self.valid = True
        self.invalid_message = None

        self.request = request
        self.text_name = form_text_name
        self.img_name = form_img_name
        self.require_text = require_text
        self.require_img = require_img
        self.validate_text = validate_text

        self.ip = get_ip_from_request(self.request)
        self.text = request.form.get(form_text_name, None)
        self.img = make_img_from_request(request, form_img_name)
        self.user = get_username()

        self.event = get_event(self.ip)
        push_event(self.ip, event=self.event)

        self.set_is_valid()

    def is_invalid_text(self):
        text_len = len(re.sub(r'\s', '', self.text))
        if text_len < MIN_POST_LENGTH or text_len > MAX_POST_LENGTH:
            return f'Min characters ({MIN_POST_LENGTH}). Max characters ({MAX_POST_LENGTH}).'

        text_row_count = self.text.count('\n')
        if text_row_count > MAX_POST_ROWS:
            return f'Max rows ({MAX_POST_ROWS})'

        return False

    def set_is_valid(self):
        assert self.invalid_message == None

        if self.require_img:
            if not self.img:
                self.invalid_message = 'No image submitted.'

        elif self.require_text:
            if not self.text:
                self.invalid_message = 'No text submitted.'
            elif self.validate_text:
                self.invalid_message = self.is_invalid_text()

        if self.invalid_message:
            self.valid = False
